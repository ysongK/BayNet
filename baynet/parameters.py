"""Parameter tables for Graph objects."""
from typing import List, Tuple, Optional, Dict, Any
from itertools import product
import numpy as np
import igraph


class ConditionalProbabilityTable:
    """Conditional probability table for categorical data."""

    def __init__(self, node: Optional[igraph.Vertex] = None) -> None:
        """Initialise a conditional probability table."""
        if node is None:
            return
        self._scaled = False
        # sorted_parents = sorted(node.neighbors(mode="in"), key = lambda x: x['name'])
        # print(sorted_parents)
        self.parent_levels = [v['levels'] for v in node.neighbors(mode="in")]
        if any([pl is None for pl in self.parent_levels]):
            raise ValueError(f"Parent of {node['name']} missing attribute 'levels'")
        self.n_parent_levels = [len(v['levels']) for v in node.neighbors(mode="in")]
        self.parents = np.array([parent.index for parent in node.neighbors(mode="in")], dtype=int)

        node_levels = node['levels']
        if node_levels is None:
            raise ValueError(f"Node {node['name']} missing attribute 'levels'")
        self.levels = node_levels
        self.n_levels = len(node_levels)

        self.array = np.zeros([*self.n_parent_levels, len(node_levels)], dtype=float)
        self.cumsum_array = np.zeros([*self.n_parent_levels, len(node_levels)], dtype=float)

    @classmethod
    def from_dict(cls, **kwargs):
        cpd = cls()
        kwargs['array'] = np.array(kwargs['array'])
        kwargs['parents'] = np.array(kwargs['parents'])
        kwargs['cumsum_array'] = np.array(kwargs['cumsum_array'])
        cpd.__dict__.update(**kwargs)
        return cpd

    def to_dict(self) -> Dict[str, Any]:
        kwargs = self.__dict__.copy()
        kwargs['array'] = self.array.tolist()
        kwargs['parents'] = self.parents.tolist()
        kwargs['cumsum_array'] = self.cumsum_array.tolist()
        return kwargs

    @property
    def parent_configurations(self) -> List[Tuple[str, ...]]:
        return list(product(*self.parent_levels))
    
    @property
    def parent_configurations_idx(self) -> List[Tuple[int, ...]]:
        int_parent_levels = [list(range(parent_levels)) for parent_levels in self.n_parent_levels]
        return list(product(*int_parent_levels))

    def rescale_probabilities(self) -> None:
        """
        Rescale probability table rows.

        Set any variables with no probabilities to be uniform,
        scale CPT rows to sum to 1, then compute cumulative sums
        to make sampling faster.
        """
        # Anywhere with sum(probs) == 0, we set to all 1 prior to scaling
        self.array[self.array.sum(axis=-1) == 0] = 1
        self.array = np.nan_to_num(self.array, nan=1e-8, posinf=1.0 - 1e-8)
        # Rescale probabilities to sum to 1
        self.array /= np.expand_dims(self.array.sum(axis=-1), axis=-1)
        self.cumsum_array = self.array.cumsum(axis=-1)
        self._scaled = True

    def sample(self, incomplete_data: np.ndarray) -> np.ndarray:
        """Sample based on parent values."""
        if not self._scaled:
            raise ValueError("CPT not scaled; use .rescale_probabilities() before sampling")
        parent_values_array = incomplete_data[:, self.parents].astype(int)
        random_vector = np.random.uniform(size=parent_values_array.shape[0])
        parent_values: List[Tuple[int, ...]] = list(map(tuple, parent_values_array))
        return _sample_cpt(self.cumsum_array, parent_values, random_vector)

    def sample_parameters(
            self,
            alpha: Optional[float] = None,
            seed: Optional[int] = None
        ) -> np.ndarray:
        """Sample CPT from dirichlet distribution."""
        if alpha is None:
            alpha = 20.0
        if seed is not None:
            np.random.seed(seed)
        parent_levels = int(np.prod(np.array(self.n_parent_levels, dtype=np.int64)))
        alpha_norm: np.float64 = np.max(
            np.array([0.01, alpha / (parent_levels * self.n_levels)])
        )
        self.array = np.random.dirichlet(np.array([alpha_norm] * self.n_levels), parent_levels).reshape(self.array.shape)
        self.rescale_probabilities()    



def _sample_cpt(
    cpt: np.ndarray, parent_values: List[Tuple[int, ...]], random_vector: np.ndarray
) -> np.ndarray:
    """Sample given cpt based on rows of parent values and random vector."""
    out_vector = np.zeros(random_vector.shape)
    for row_idx in range(random_vector.shape[0]):
        probs = cpt[parent_values[row_idx]]
        out_vector[row_idx] = np.argmax(random_vector[row_idx] < probs)
    return out_vector


class ConditionalProbabilityDistribution:
    """Conditional probability distribution for continuous data."""

    def __init__(self, node: Optional[igraph.Vertex] = None, mean: Optional[float] = None, std: Optional[float] = None) -> None:
        """Initialise a conditional probability table."""
        if mean is None:
            mean = 0.0
        self.mean = mean
        if std is None:
            std = 1.0
        self.std = std
        if node is None:
            return
        self.parents = np.array([parent.index for parent in node.neighbors(mode="in")], dtype=int)
        self.array = np.zeros(len(self.parents), dtype=float)

    @classmethod
    def from_dict(cls, **kwargs):
        cpd = cls()
        kwargs['array'] = np.array(kwargs['array'])
        kwargs['parents'] = np.array(kwargs['parents'])
        cpd.__dict__.update(**kwargs)
        return cpd

    def to_dict(self) -> Dict[str, Any]:
        kwargs = self.__dict__.copy()
        kwargs['array'] = self.array.tolist()
        kwargs['parents'] = self.parents.tolist()
        return kwargs

    def sample_parameters(
        self, weights: Optional[List[float]] = None, seed: Optional[int] = None
    ) -> None:
        """Sample parent weights uniformly from defined possible values."""
        if seed is not None:
            np.random.seed(seed)
        if weights is None:
            weights = [-2.0, -0.5, 0.5, 2.0]
        self.array = np.random.choice(weights, len(self.parents))

    def sample(self, incomplete_data: np.ndarray) -> np.ndarray:
        """Sample column based on parent columns in incomplete data matrix."""
        noise = np.random.normal(loc=self.mean, scale=self.std, size=incomplete_data.shape[0])
        if len(self.parents) == 0:
            return noise
        parent_values = incomplete_data[:, self.parents]
        return parent_values.dot(self.array) + noise
