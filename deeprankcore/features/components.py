import logging
from typing import Optional

import numpy as np

from deeprankcore.domain import nodestorage as Nfeat
from deeprankcore.molstruct.atom import Atom
from deeprankcore.molstruct.residue import Residue
from deeprankcore.molstruct.variant import SingleResidueVariant
from deeprankcore.utils.graph import Graph
from deeprankcore.utils.parsing import atomic_forcefield

_log = logging.getLogger(__name__)

def add_features( # pylint: disable=unused-argument
    pdb_path: str, graph: Graph,
    single_amino_acid_variant: Optional[SingleResidueVariant] = None
    ):

    for node in graph.nodes:
        if isinstance(node.id, Residue):
            residue = node.id
        elif isinstance(node.id, Atom):
            atom = node.id
            residue = atom.residue
            
            node.features[Nfeat.ATOMTYPE] = atom.element.onehot
            node.features[Nfeat.PDBOCCUPANCY] = atom.occupancy
            node.features[Nfeat.ATOMCHARGE] = atomic_forcefield.get_charge(atom)
        else:
            raise TypeError(f"Unexpected node type: {type(node.id)}") 

        node.features[Nfeat.RESTYPE] = residue.amino_acid.onehot
        node.features[Nfeat.RESCHARGE] = residue.amino_acid.charge
        node.features[Nfeat.POLARITY] = residue.amino_acid.polarity.onehot
        node.features[Nfeat.RESSIZE] = residue.amino_acid.size
        node.features[Nfeat.RESMASS] = residue.amino_acid.mass
        node.features[Nfeat.RESPI] = residue.amino_acid.pI
        node.features[Nfeat.HBDONORS] = residue.amino_acid.hydrogen_bond_donors
        node.features[Nfeat.HBACCEPTORS] = residue.amino_acid.hydrogen_bond_acceptors


        if single_amino_acid_variant is not None:
            wildtype = single_amino_acid_variant.wildtype_amino_acid
            variant = single_amino_acid_variant.variant_amino_acid

            if residue == single_amino_acid_variant.residue:
                node.features[Nfeat.VARIANTRES] = variant.onehot
                node.features[Nfeat.DIFFCHARGE] = variant.charge - wildtype.charge
                node.features[Nfeat.DIFFPOLARITY] = variant.polarity.onehot - wildtype.polarity.onehot
                node.features[Nfeat.DIFFSIZE] = variant.size - wildtype.size
                node.features[Nfeat.DIFFMASS] = variant.mass - wildtype.mass
                node.features[Nfeat.DIFFPI] = variant.pI - wildtype.pI
                node.features[Nfeat.DIFFHBDONORS] = variant.hydrogen_bond_donors - wildtype.hydrogen_bond_donors
                node.features[Nfeat.DIFFHBACCEPTORS] = variant.hydrogen_bond_acceptors - wildtype.hydrogen_bond_acceptors
            else:
                node.features[Nfeat.VARIANTRES] = residue.amino_acid.onehot
                node.features[Nfeat.DIFFCHARGE] = 0
                node.features[Nfeat.DIFFPOLARITY] = np.zeros(residue.amino_acid.polarity.onehot.shape)
                node.features[Nfeat.DIFFSIZE] = 0
                node.features[Nfeat.DIFFMASS] = 0
                node.features[Nfeat.DIFFPI] = 0
                node.features[Nfeat.DIFFHBDONORS] = 0
                node.features[Nfeat.DIFFHBACCEPTORS] = 0
