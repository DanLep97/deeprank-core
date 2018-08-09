import sys, os
import torch
import numpy as np
from torch_geometric.data.dataset import Dataset
from torch_geometric.data.data import Data
from tqdm import tqdm
import h5py

class HDF5DataSet(Dataset):

    def __init__(self,root,database=None,transform=None,pre_transform=None,
                dict_filter = None, target='dockQ',tqdm = True, index=None,
                node_feature='all', edge_feature = 'all',
                edge_feature_transform=lambda x: np.tanh(-x/2+2)+1):
        super().__init__(root,transform,pre_transform)

        # allow for multiple database
        self.database = database
        if not isinstance(database,list):
            self.database = [database]

        self.target = target
        self.dict_filter = dict_filter
        self.tqdm = tqdm
        self.index = index
        self.node_feature = node_feature
        self.edge_feature = edge_feature

        self.edge_feature_transform = edge_feature_transform

        # check if the files are ok
        self.check_hdf5_files()

        # check the selection of features
        self.check_node_feature()
        self.check_edge_feature()

        # create the indexing system
        # alows to associate each mol to an index
        # and get fname and mol name from the index
        self.create_index_molecules()


    def __len__(self):
        """Get the length of the dataset
        Returns:
            int: number of complexes in the dataset
        """
        return len(self.index_complexes)


    def _download(self):
        pass

    def _process(self):
        pass

    def get(self,index):
        """Get one item from its unique index.
        Args:
            index (int): index of the complex
        Returns:
            dict: {'mol':[fname,mol],'feature':feature,'target':target}
        """

        fname,mol = self.index_complexes[index]
        data = self.load_one_graph(fname,mol)
        return data


    def check_hdf5_files(self):
        """Check if the data contained in the hdf5 file is ok."""

        print("   Checking dataset Integrity")
        remove_file = []
        for fname in self.database:
            try:
                f = h5py.File(fname,'r')
                mol_names = list(f.keys())
                if len(mol_names) == 0:
                    print('    -> %s is empty ' %fname)
                    remove_file.append(fname)
                f.close()
            except Exception as e:
                print(e)
                print('    -> %s is corrputed ' %fname)
                remove_file.append(fname)

        for name in remove_file:
            self.database.remove(name)


    def check_node_feature(self):

        f = h5py.File(self.database[0],'r')
        mol_key = list(f.keys())[0]
        self.available_node_feature = list(f[mol_key+'/node_data/'].keys())
        f.close()

        if self.node_feature == 'all':
            self.node_feature = self.available_node_feature
        else:
            for feat in self.node_feature:
                if feat not in self.available_node_feature:
                        print(feat, ' node feature not found in the file', self.database[0])
                        print('Possible node feature : ')
                        print('\n'.join(self.available_node_feature))
                        #raise ValueError('Feature Not found')
                        exit()

    def check_edge_feature(self):

        f = h5py.File(self.database[0],'r')
        mol_key = list(f.keys())[0]
        self.available_edge_feature = list(f[mol_key+'/edge_data/'].keys())
        f.close()

        if self.edge_feature == 'all':
            self.edge_feature = self.available_edge_feature
        elif self.edge_feature is not None:
            for feat in self.edge_feature:
                if feat not in self.available_edge_feature:
                    print(feat, ' edge attribute not found in the file', self.database[0])
                    print('Possible edge attribute : ')
                    print('\n'.join(self.available_edge_feature))
                    #raise ValueError('Feature Not found')
                    exit()

    def load_one_graph(self,fname,mol):

        #print('Load mol :', mol)

        f5 = h5py.File(fname,'r')
        grp = f5[mol]

        #nodes
        data = ()
        for feat in self.node_feature:
            vals = grp['node_data/'+feat].value
            if vals.ndim == 1:
                vals = vals.reshape(-1,1)
            data += (vals,)
        x = torch.tensor(np.hstack(data),dtype=torch.float)

        # index ! we have to have all the edges i.e : (i,j) and (j,i)
        ind = grp['edge_index'].value
        ind = np.vstack((ind,np.flip(ind,1))).T
        edge_index = torch.tensor(ind,dtype=torch.long)

        # edge feature (same issue than above)
        data = ()
        if self.edge_feature is not None:
            for feat in self.edge_feature:
                vals = grp['edge_data/'+feat].value
                if vals.ndim == 1:
                    vals = vals.reshape(-1,1)
                data += (vals,)
            data = np.hstack(data)
            data = np.vstack((data,data))
            data = self.edge_feature_transform(data)
            edge_attr = torch.tensor(data,dtype=torch.float)

        else:
            edge_attr = None

        #internal edges
        ind = grp['internal_edge_index'].value
        ind = np.vstack((ind,np.flip(ind,1))).T
        internal_edge_index = torch.tensor(ind,dtype=torch.long)

        # internal edge feature
        data = ()
        if self.edge_feature is not None:
            for feat in self.edge_feature:
                vals = grp['internal_edge_data/'+feat].value
                if vals.ndim == 1:
                    vals = vals.reshape(-1,1)
                data += (vals,)
            data = np.hstack(data)
            data = np.vstack((data,data))
            data = self.edge_feature_transform(data)
            internal_edge_attr = torch.tensor(data,dtype=torch.float)

        else:
            internal_edge_attr = None


        #target
        y = torch.tensor([grp['score/'+self.target].value],dtype=torch.float)

        #pos
        pos = torch.tensor(grp['node_data/pos/'].value,dtype=torch.float)

        # load
        data = Data(x = x,
                    edge_index = edge_index,
                    edge_attr = edge_attr,
                    y = y,
                    pos=pos)

        data.internal_edge_index = internal_edge_index
        data.internal_edge_attr = internal_edge_attr

        f5.close()
        return data

    def create_index_molecules(self):
        '''Create the indexing of each molecule in the dataset.
        Create the indexing: [ ('1ak4.hdf5,1AK4_100w),...,('1fqj.hdf5,1FGJ_400w)]
        This allows to refer to one complex with its index in the list
        '''
        print("   Processing data set")

        self.index_complexes = []

        desc = '{:25s}'.format('   Train dataset')
        if self.tqdm:
            data_tqdm = tqdm(self.database,desc=desc,file=sys.stdout)
        else:
            print('   Train dataset')
            data_tqdm = self.database
        sys.stdout.flush()

        for fdata in data_tqdm:
            if self.tqdm:
                data_tqdm.set_postfix(mol=os.path.basename(fdata))
            try:
                fh5 = h5py.File(fdata,'r')
                if self.index is None:
                    mol_names = list(fh5.keys())
                else:
                    mol_names = [list(fh5.keys())[i] for i in self.index]
                for k in mol_names:
                    if self.filter(fh5[k]):
                        self.index_complexes += [(fdata,k)]
                fh5.close()
            except Exception as inst:
                print('\t\t-->Ignore File : ' + fdata)
                print(inst)

        self.ntrain = len(self.index_complexes)
        self.index_train = list(range(self.ntrain))
        self.ntot = len(self.index_complexes)

    def filter(self,molgrp):
        '''Filter the molecule according to a dictionary.
        The filter is based on the attribute self.dict_filter
        that must be either of the form: { 'name' : cond } or None
        Args:
            molgrp (str): group name of the molecule in the hdf5 file
        Returns:
            bool: True if we keep the complex False otherwise
        Raises:
            ValueError: If an unsuported condition is provided
        '''
        if self.dict_filter is None:
            return True

        for cond_name,cond_vals in self.dict_filter.items():

            try:
                val = molgrp[cond_name].value
            except KeyError:
                print('   :Filter %s not found for mol %s' %(cond_name,mol))

            # if we have a string it's more complicated
            if isinstance(cond_vals,str):

                ops = ['>','<','==']
                new_cond_vals = cond_vals
                for o in ops:
                    new_cond_vals = new_cond_vals.replace(o,'val'+o)
                if not eval(new_cond_vals):
                    return False
            else:
                raise ValueError('Conditions not supported', cond_vals)

        return True


if __name__ == '__main__':

    dataset = HDF5DataSet(root='./',database='test.hdf5',
                          node_feature='all', edge_feature = ['dist'])
    dataset.get(0)