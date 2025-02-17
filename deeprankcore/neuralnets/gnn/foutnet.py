import torch
import torch.nn.functional as F
from torch import nn
from torch.nn import Parameter
from torch_geometric.nn import max_pool_x
from torch_geometric.nn.inits import uniform
from torch_scatter import scatter_mean

from deeprankcore.utils.community_pooling import (community_pooling,
                                                  get_preloaded_cluster)


class FoutLayer(torch.nn.Module):

    """
    This layer is described by eq. (1) of
    Protein Interface Predition using Graph Convolutional Network
    by Alex Fout et al. NIPS 2018

    Args:
        in_channels (int): Size of each input sample.
        out_channels (int): Size of each output sample.
        bias (bool, optional): If set to :obj:`False`, the layer will not learn
            an additive bias. Defaults to True.
    """

    def __init__(self, in_channels: int, out_channels: int, bias: bool = True):

        super().__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels

        # Wc and Wn are the center and neighbor weight matrix
        self.wc = Parameter(torch.Tensor(in_channels, out_channels))
        self.wn = Parameter(torch.Tensor(in_channels, out_channels))

        if bias:
            self.bias = Parameter(torch.Tensor(out_channels))
        else:
            self.register_parameter("bias", None)

        self.reset_parameters()

    def reset_parameters(self):
        size = self.in_channels
        uniform(size, self.wc)
        uniform(size, self.wn)
        uniform(size, self.bias)

    def forward(self, x, edge_index):

        num_node = len(x)

        # alpha = x * Wc
        alpha = torch.mm(x, self.wc)

        # beta = x * Wn
        beta = torch.mm(x, self.wn)

        # gamma_i = 1/Ni Sum_j x_j * Wn
        # there might be a better way than looping over the nodes
        gamma = torch.zeros(num_node, self.out_channels).to(alpha.device)
        for n in range(num_node):
            index = edge_index[:, edge_index[0, :] == n][1, :]
            gamma[n, :] = torch.mean(beta[index, :], dim=0)

        # alpha = alpha + gamma
        alpha = alpha + gamma

        # add the bias
        if self.bias is not None:
            alpha = alpha + self.bias

        return alpha

    def __repr__(self):
        return f"{self.__class__.__name__}({self.in_channels}, {self.out_channels})"


class FoutNet(torch.nn.Module):
    def __init__(self, input_shape, output_shape=1, input_shape_edge=None): # pylint: disable=unused-argument
        super().__init__()

        self.conv1 = FoutLayer(input_shape, 16)
        self.conv2 = FoutLayer(16, 32)

        self.fc1 = torch.nn.Linear(32, 64)
        self.fc2 = torch.nn.Linear(64, output_shape)

        self.clustering = "mcl"

    def forward(self, data):

        act = nn.Tanhshrink()
        act = F.relu
        # act = nn.LeakyReLU(0.25)

        # first conv block
        data.x = act(self.conv1(data.x, data.edge_index))
        cluster = get_preloaded_cluster(data.cluster0, data.batch)
        data = community_pooling(cluster, data)

        # second conv block
        data.x = act(self.conv2(data.x, data.edge_index))
        cluster = get_preloaded_cluster(data.cluster1, data.batch)
        x, batch = max_pool_x(cluster, data.x, data.batch)

        # FC
        x = scatter_mean(x, batch, dim=0)
        x = act(self.fc1(x))
        x = self.fc2(x)
        # x = F.dropout(x, training=self.training)

        return x
        # return F.relu(x)
