from baynet.utils import DAG_pb2
import baynet
import igraph
import numpy as np
import pyparsing
from baynet.parameters import ConditionalProbabilityDistribution, ConditionalProbabilityTable


def dag_to_buf(dag: 'baynet.DAG') -> bytes:
    dag_buf = DAG_pb2.DAG()
    for vertex in dag.vs:
        node = DAG_pb2.Node()
        node.name = vertex['name']
        node.parents.extend([str(v['name']) for v in vertex.neighbors(mode="in")])
        if vertex['CPD'] is not None:
            if isinstance(vertex['CPD'], ConditionalProbabilityTable):
                node.variable_type = DAG_pb2.NodeType.DISCRETE
                node.levels.extend(vertex['levels'])
            elif isinstance(vertex['CPD'], ConditionalProbabilityDistribution):
                node.variable_type = DAG_pb2.NodeType.CONTINUOUS
            node.cpd_array.shape.extend(vertex['CPD'].array.shape)
            node.cpd_array.flat_array = vertex['CPD'].array.tobytes()
        dag_buf.nodes.append(node)
    return dag_buf.SerializeToString()


def buf_to_dag(dag_buf: bytes) -> 'baynet.DAG':
    dag_from_buf = DAG_pb2.DAG.FromString(dag_buf)
    dag = baynet.DAG()
    dag.add_vertices([node.name for node in dag_from_buf.nodes])
    for buf_node in dag_from_buf.nodes:
        edges = [(source, buf_node.name) for source in buf_node.parents]
        dag.add_edges(edges)
        node = dag.get_node(buf_node.name)
        if buf_node.variable_type == DAG_pb2.NodeType.DISCRETE:
            node['levels'] = list(buf_node.levels)
            cpd = ConditionalProbabilityTable()
            cpd.levels = list(buf_node.levels)
            cpd.array = buf_to_array(buf_node.cpd_array)
            cpd.rescale_probabilities()
        elif buf_node.variable_type == DAG_pb2.NodeType.CONTINUOUS:
            cpd = ConditionalProbabilityDistribution()
            cpd.array = buf_to_array(buf_node.cpd_array)
        cpd.parents = list(buf_node.parents)
        node['CPD'] = cpd
    return dag


def buf_to_array(array_buf: DAG_pb2.Array) -> np.ndarray:
    arr = np.frombuffer(array_buf.flat_array)
    if arr.size > 0:
        arr = arr.reshape(list(array_buf.shape))
    return arr


def dag_from_bif(bif_str: str):
    return bif_str
