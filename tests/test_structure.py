from time import time
from pathlib import Path

import pytest
import networkx as nx
import numpy as np
import yaml

from baynet.structure import DAG, _nodes_sorted, _nodes_from_modelstring, _edges_from_modelstring
from baynet.parameters import ConditionalProbabilityDistribution


def test_nodes_sorted():
    nodes = ["a", "B", "aa", 1, 2]
    assert _nodes_sorted(nodes) == ["1", "2", "B", "a", "aa"]


def test_nodes_from_modelstring(test_modelstring):
    assert _nodes_from_modelstring(test_modelstring) == ["A", "B", "C", "D"]


def test_edges_from_modelstring(test_modelstring):
    assert _edges_from_modelstring(test_modelstring) == [("C", "B"), ("D", "B"), ("D", "C")]


def test_DAG_from_modelstring(test_dag):
    dag = test_dag
    assert dag.nodes == {"A", "B", "C", "D"}
    assert dag.edges == dag.directed_edges == {("C", "B"), ("D", "B"), ("D", "C")}


def test_DAG_from_amat():
    unconnected_amat = np.zeros((4, 4))
    unconnected_graph = DAG.from_amat(unconnected_amat, list("ABCD"))
    unconnected_graph_list = DAG.from_amat(unconnected_amat.tolist(), list("ABCD"))
    fully_connected_amat = np.tril(np.ones((4, 4)), -1)
    fully_connected_graph = DAG.from_amat(fully_connected_amat, list("ABCD"))

    with pytest.raises(ValueError):
        DAG.from_amat(unconnected_amat, ["A", "B", "C"])
    with pytest.raises(ValueError):
        DAG.from_amat(unconnected_amat, "ABCD")

    assert np.all(unconnected_graph.get_numpy_adjacency() == unconnected_amat)
    assert np.all(unconnected_graph_list.get_numpy_adjacency() == unconnected_amat)
    assert np.all(fully_connected_graph.get_numpy_adjacency() == fully_connected_amat)

    assert fully_connected_graph.nodes == unconnected_graph.nodes == {"A", "B", "C", "D"}
    assert unconnected_graph.edges == set()
    assert (
        fully_connected_graph.edges
        == fully_connected_graph.directed_edges
        == {('C', 'A'), ('B', 'A'), ('D', 'B'), ('D', 'C'), ('D', 'A'), ('C', 'B'),}
    )


def test_DAG_from_other():
    test_graph = nx.DiGraph()
    test_graph.add_nodes_from(list("ABCD"))
    edges = [("C", "B"), ("D", "B"), ("D", "C")]
    test_graph.add_edges_from(edges)
    graph = DAG.from_other(test_graph)
    assert graph.edges == graph.directed_edges == set(edges)
    assert graph.nodes == set(list("ABCD"))


def test_DAG_dtype(test_dag):
    dag = test_dag
    assert dag.dtype == None
    dag.generate_continuous_parameters()
    assert dag.dtype == "continuous"
    dag.generate_discrete_parameters()
    assert dag.dtype == "discrete"
    dag.vs[0]['CPD'] = ConditionalProbabilityDistribution(dag.vs[0])
    assert dag.dtype == "mixed"


def test_DAG_edge_properties(test_dag):
    dag = test_dag
    forward = {("C", "B"), ("D", "B"), ("D", "C")}
    backward = {("B", "C"), ("B", "D"), ("C", "D")}
    assert dag.edges == dag.directed_edges == forward
    assert dag.reversed_edges == backward
    assert dag.as_undirected().edges == dag.skeleton_edges == forward | backward


def test_DAG_add_edge(test_dag):
    dag = test_dag
    dag.add_edge("B", "A")
    assert dag.edges == {("C", "B"), ("D", "B"), ("D", "C"), ("B", "A")}


def test_DAG_adding_duplicates(test_dag):
    dag = test_dag
    with pytest.raises(ValueError):
        dag.add_edge("C", "B")
    with pytest.raises(ValueError):
        dag.add_edges([("C", "B")])
    with pytest.raises(ValueError):
        dag.add_edges([("D", "A"), ("D", "A")])


def test_DAG_get_numpy_adjacency(test_dag):
    dag = test_dag
    amat = np.array(
        [
            [False, False, False, False],
            [False, False, False, False],
            [False, True, False, False],
            [False, True, True, False],
        ],
        dtype=bool,
    )
    assert np.all(dag.get_numpy_adjacency() == amat)
    assert np.all(dag.get_numpy_adjacency(skeleton=True) == amat | amat.T)


def test_DAG_get_modelstring(test_dag, test_modelstring, reversed_dag, reversed_modelstring):
    assert test_dag.get_modelstring() == test_modelstring
    assert reversed_dag.get_modelstring() == reversed_modelstring


def test_DAG_get_ancestors(test_dag):
    dag = test_dag
    assert (
        dag.get_ancestors("A")['name']
        == dag.get_ancestors(dag.vs[0])['name']
        == dag.get_ancestors(0)['name']
        == []
    )
    assert (
        dag.get_ancestors("B")['name']
        == dag.get_ancestors(dag.vs[1])['name']
        == dag.get_ancestors(1)['name']
        == ['C', 'D']
    )
    assert (
        dag.get_ancestors("C")['name']
        == dag.get_ancestors(dag.vs[2])['name']
        == dag.get_ancestors(2)['name']
        == ['D']
    )
    assert (
        dag.get_ancestors("D")['name']
        == dag.get_ancestors(dag.vs[3])['name']
        == dag.get_ancestors(3)['name']
        == []
    )


def test_DAG_get_descendants(reversed_dag):
    dag = reversed_dag
    assert (
        dag.get_descendants("A")['name']
        == dag.get_descendants(dag.vs[0])['name']
        == dag.get_descendants(0)['name']
        == []
    )
    assert (
        dag.get_descendants("B")['name']
        == dag.get_descendants(dag.vs[1])['name']
        == dag.get_descendants(1)['name']
        == ['C', 'D']
    )
    assert (
        dag.get_descendants("C")['name']
        == dag.get_descendants(dag.vs[2])['name']
        == dag.get_descendants(2)['name']
        == ['D']
    )
    assert (
        dag.get_descendants("D")['name']
        == dag.get_descendants(dag.vs[3])['name']
        == dag.get_descendants(3)['name']
        == []
    )


def test_DAG_get_node_name_or_index(test_dag):
    dag = test_dag
    for name, index in zip("ABCD", range(4)):
        assert dag.get_node_name(index) == name
        assert dag.get_node_index(name) == index


def test_DAG_are_neighbours(test_dag):
    dag = test_dag
    a, b, c, d = dag.vs
    assert not dag.are_neighbours(a, b)
    assert not dag.are_neighbours(a, c)
    assert not dag.are_neighbours(a, d)
    assert dag.are_neighbours(b, c)
    assert dag.are_neighbours(b, d)
    assert dag.are_neighbours(c, d)


def test_DAG_get_v_structures(test_dag, reversed_dag, partial_dag):
    dag = test_dag
    assert partial_dag.get_v_structures() == {("C", "B", "D")}
    assert dag.get_v_structures() == set()
    assert dag.get_v_structures(True) == {("C", "B", "D")}
    assert reversed_dag.get_v_structures(True) == {("B", "D", "C")}


def test_DAG_yaml_continuous_file(temp_out, test_dag):
    dag_path = temp_out / 'cont.pb'
    dag = test_dag
    dag.generate_continuous_parameters()
    dag.save(dag_path)
    dag2 = DAG.load(dag_path)
    assert dag.nodes == dag2.nodes
    assert dag.edges == dag2.edges


def test_DAG_yaml_continuous_str(test_dag):
    dag = test_dag
    dag.generate_continuous_parameters()
    dag_string = dag.save()
    dag2 = DAG.load(dag_string)
    assert dag.nodes == dag2.nodes
    assert dag.edges == dag2.edges


def test_DAG_yaml_discrete_file(temp_out, test_dag):
    dag_path = temp_out / 'cont.pb'
    dag = test_dag
    dag.generate_discrete_parameters(seed=0)
    dag.save(dag_path)
    dag2 = DAG.load(dag_path)
    assert dag.nodes == dag2.nodes
    assert dag.edges == dag2.edges


def test_DAG_yaml_discrete_str(test_dag):
    dag = test_dag
    dag.generate_discrete_parameters(seed=0)
    dag_string = dag.save()
    dag2 = DAG.load(dag_string)
    assert dag.nodes == dag2.nodes
    assert dag.edges == dag2.edges


def test_DAG_generate_parameters(test_dag):
    dag = test_dag
    dag.generate_continuous_parameters(possible_weights=[1], std=0.0)
    for v in dag.vs:
        assert np.allclose(v['CPD'].array, 1)

    for levels in [["0", "1"], ["0", "1", "2"]]:
        dag.vs['levels'] = [levels for v in dag.vs]
        dag.generate_discrete_parameters()
        assert dag.vs[0]['CPD'].array.shape == (len(levels),)
        assert dag.vs[1]['CPD'].array.shape == (len(levels), len(levels), len(levels))
        assert dag.vs[2]['CPD'].array.shape == (len(levels), len(levels))
        assert dag.vs[3]['CPD'].array.shape == (len(levels),)


def test_DAG_sample_continuous(test_dag):
    dag = test_dag
    dag.generate_continuous_parameters(std=0.0)
    assert np.allclose(dag.sample(10).values.astype(int), 0)

    dag.generate_continuous_parameters(std=1.0)
    assert not np.allclose(dag.sample(10, seed=1).values.astype(int), 0)


def test_DAG_sample_discrete(test_dag):
    dag = test_dag
    dag.generate_discrete_parameters()
    assert not np.allclose(dag.sample(10, seed=1).values.astype(int), 0)


def test_DAG_remove_nodes(test_dag):
    dag = test_dag
    dag.generate_discrete_parameters()
    dag.remove_nodes(['C'])
    assert dag.get_node('B')['CPD'].parents == ['D']


def test_DAG_mutilate(test_dag):
    dag = test_dag
    dag.generate_discrete_parameters(max_levels=2)
    dag = dag.mutilate("C", "1")
    c_cpt = dag.get_node('C')['CPD']
    assert c_cpt.parents == []
    assert np.all(c_cpt.array == [0, 1])
    assert all(dag.sample(100)['C'] == '1')
    assert dag.get_node('B')['CPD'].parents == ["C"]
    assert dag.get_node('B')['CPD'].array.shape == (2, 2)
    with pytest.raises(KeyError):
        dag.get_node('D')


def test_Graph():
    from baynet import Graph

    g = Graph()


if __name__ == "__main__":
    from baynet.utils.dag_io import dag_from_bif

    bif_path = Path(__file__).parent.parent / 'alarm.bif'

    dag = dag_from_bif(bif_path.open().read())

