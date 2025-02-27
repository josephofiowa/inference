import networkx as nx
import pytest

from inference.enterprise.deployments.complier.graph_parser import (
    add_input_nodes_for_graph,
    add_output_nodes_for_graph,
    add_steps_nodes_for_graph,
    construct_graph,
    get_nodes_that_are_reachable_from_pointed_ones_in_reversed_graph,
    prepare_execution_graph,
    verify_each_node_reach_at_least_one_output,
)
from inference.enterprise.deployments.constants import (
    INPUT_NODE_KIND,
    OUTPUT_NODE_KIND,
    STEP_NODE_KIND,
)
from inference.enterprise.deployments.entities.deployment_specs import DeploymentSpecV1
from inference.enterprise.deployments.entities.inputs import (
    InferenceImage,
    InferenceParameter,
)
from inference.enterprise.deployments.entities.outputs import JsonField
from inference.enterprise.deployments.entities.steps import Crop, ObjectDetectionModel
from inference.enterprise.deployments.errors import (
    AmbiguousPathDetected,
    InvalidStepInputDetected,
    NodesNotReachingOutputError,
    NotAcyclicGraphError,
    SelectorToUndefinedNodeError,
)


def test_add_input_nodes_for_graph() -> None:
    # given
    execution_graph = nx.DiGraph()
    inputs = [
        InferenceImage(type="InferenceImage", name="image"),
        InferenceParameter(type="InferenceParameter", name="x"),
        InferenceParameter(type="InferenceParameter", name="y"),
    ]

    # when
    execution_graph = add_input_nodes_for_graph(
        inputs=inputs,
        execution_graph=execution_graph,
    )

    # then
    assert execution_graph.nodes["$inputs.image"]["kind"] == INPUT_NODE_KIND
    assert execution_graph.nodes["$inputs.image"]["definition"] == inputs[0]
    assert execution_graph.nodes["$inputs.x"]["kind"] == INPUT_NODE_KIND
    assert execution_graph.nodes["$inputs.x"]["definition"] == inputs[1]
    assert execution_graph.nodes["$inputs.y"]["kind"] == INPUT_NODE_KIND
    assert execution_graph.nodes["$inputs.y"]["definition"] == inputs[2]


def test_add_steps_nodes_for_graph() -> None:
    # given
    execution_graph = nx.DiGraph()
    steps = [
        Crop(
            type="Crop",
            name="my_crop",
            image="$inputs.image",
            detections="$steps.detect_2.predictions",
        ),
        ObjectDetectionModel(
            type="ObjectDetectionModel",
            name="my_model",
            image="$inputs.image",
            model_id="some/1",
            confidence=0.3,
        ),
    ]

    # when
    execution_graph = add_steps_nodes_for_graph(
        steps=steps,
        execution_graph=execution_graph,
    )

    # then
    assert execution_graph.nodes["$steps.my_crop"]["kind"] == STEP_NODE_KIND
    assert execution_graph.nodes["$steps.my_crop"]["definition"] == steps[0]
    assert execution_graph.nodes["$steps.my_model"]["kind"] == STEP_NODE_KIND
    assert execution_graph.nodes["$steps.my_model"]["definition"] == steps[1]


def test_add_output_nodes_for_graph() -> None:
    # given
    execution_graph = nx.DiGraph()
    outputs = [
        JsonField(type="JsonField", name="some", selector="$steps.a.predictions"),
        JsonField(type="JsonField", name="other", selector="$steps.b.predictions"),
    ]

    # when
    execution_graph = add_output_nodes_for_graph(
        outputs=outputs,
        execution_graph=execution_graph,
    )

    # then
    assert execution_graph.nodes["$outputs.some"]["kind"] == OUTPUT_NODE_KIND
    assert execution_graph.nodes["$outputs.some"]["definition"] == outputs[0]
    assert execution_graph.nodes["$outputs.other"]["kind"] == OUTPUT_NODE_KIND
    assert execution_graph.nodes["$outputs.other"]["definition"] == outputs[1]


def test_construct_graph() -> None:
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
                {"type": "InferenceParameter", "name": "confidence"},
            ],
            "steps": [
                {
                    "type": "ClassificationModel",
                    "name": "step_1",
                    "image": "$inputs.image",
                    "model_id": "vehicle-classification-eapcd/2",
                    "confidence": "$inputs.confidence",
                },
                {
                    "type": "Condition",
                    "name": "step_2",
                    "left": "$steps.step_1.top",
                    "operator": "equal",
                    "right": "Car",
                    "step_if_true": "$steps.step_3",
                    "step_if_false": "$steps.step_4",
                },
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_3",
                    "image": "$inputs.image",
                    "model_id": "yolov8n-640",
                    "confidence": 0.5,
                    "iou_threshold": 0.4,
                },
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_4",
                    "image": "$inputs.image",
                    "model_id": "yolov8n-1280",
                    "confidence": 0.5,
                    "iou_threshold": 0.4,
                },
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "top_class",
                    "selector": "$steps.step_1.top",
                },
                {
                    "type": "JsonField",
                    "name": "step_3_predictions",
                    "selector": "$steps.step_3.predictions",
                },
                {
                    "type": "JsonField",
                    "name": "step_4_predictions",
                    "selector": "$steps.step_4.predictions",
                },
            ],
        }
    )

    # when
    result = construct_graph(deployment_spec=deployment_specs)

    # then
    assert (
        result.nodes["$inputs.image"]["definition"].name == "image"
    ), "Image node must be named correctly"
    assert (
        result.nodes["$inputs.confidence"]["definition"].name == "confidence"
    ), "Input confidence node must be named correctly"
    assert (
        result.nodes["$steps.step_1"]["definition"].name == "step_1"
    ), "Step 1 node must be named correctly"
    assert (
        result.nodes["$steps.step_2"]["definition"].name == "step_2"
    ), "Step 2 node must be named correctly"
    assert (
        result.nodes["$steps.step_3"]["definition"].name == "step_3"
    ), "Step 3 node must be named correctly"
    assert (
        result.nodes["$steps.step_4"]["definition"].name == "step_4"
    ), "Step 4 node must be named correctly"
    assert (
        result.nodes["$outputs.top_class"]["definition"].selector == "$steps.step_1.top"
    ), "Output must be installed correctly"
    assert (
        result.nodes["$outputs.step_3_predictions"]["definition"].selector
        == "$steps.step_3.predictions"
    ), "Output must be installed correctly"
    assert (
        result.nodes["$outputs.step_4_predictions"]["definition"].selector
        == "$steps.step_4.predictions"
    ), "Output must be installed correctly"
    assert result.has_edge(
        "$inputs.image", "$steps.step_1"
    ), "Image must be connected with step 1"
    assert result.has_edge(
        "$inputs.confidence", "$steps.step_1"
    ), "Confidence parameter must be connected with step 1"
    assert result.has_edge(
        "$inputs.image", "$steps.step_3"
    ), "Image must be connected with step 3"
    assert result.has_edge(
        "$inputs.image", "$steps.step_4"
    ), "Image must be connected with step 4"
    assert result.has_edge(
        "$steps.step_1", "$steps.step_2"
    ), "Object detection node must be connected with Condition step"
    assert result.has_edge(
        "$steps.step_2", "$steps.step_3"
    ), "Condition step must be connected with step 3"
    assert result.has_edge(
        "$steps.step_2", "$steps.step_4"
    ), "Condition step must be connected with step 4"
    assert result.has_edge(
        "$steps.step_1", "$outputs.top_class"
    ), "Step 1 must be connected to top_class output"
    assert result.has_edge(
        "$steps.step_3", "$outputs.step_3_predictions"
    ), "Step 3 must be connected to step_3_predictions output"
    assert result.has_edge(
        "$steps.step_4", "$outputs.step_4_predictions"
    ), "Step 4 must be connected to step_4_predictions output"
    assert len(result.edges) == 10, "10 edges in total should be created"


def test_verify_each_node_reach_at_least_one_output_when_graph_is_valid() -> None:
    # given
    execution_graph = nx.DiGraph()
    execution_graph.add_node("a", kind=INPUT_NODE_KIND)
    execution_graph.add_node("b", kind=INPUT_NODE_KIND)
    execution_graph.add_node("c", kind=STEP_NODE_KIND)
    execution_graph.add_node("d", kind=STEP_NODE_KIND)
    execution_graph.add_node("e", kind=OUTPUT_NODE_KIND)
    execution_graph.add_node("f", kind=OUTPUT_NODE_KIND)
    execution_graph.add_edge("a", "c")
    execution_graph.add_edge("b", "d")
    execution_graph.add_edge("c", "e")
    execution_graph.add_edge("d", "f")

    # when
    verify_each_node_reach_at_least_one_output(execution_graph=execution_graph)

    # then - no error raised


def test_verify_each_node_reach_at_least_one_output_when_graph_is_invalid() -> None:
    # given
    execution_graph = nx.DiGraph()
    execution_graph.add_node("a", kind=INPUT_NODE_KIND)
    execution_graph.add_node("b", kind=INPUT_NODE_KIND)
    execution_graph.add_node("c", kind=STEP_NODE_KIND)
    execution_graph.add_node("d", kind=STEP_NODE_KIND)
    execution_graph.add_node("e", kind=OUTPUT_NODE_KIND)
    execution_graph.add_edge("a", "c")
    execution_graph.add_edge("b", "d")
    execution_graph.add_edge("c", "e")

    # when
    with pytest.raises(NodesNotReachingOutputError):
        verify_each_node_reach_at_least_one_output(execution_graph=execution_graph)


def test_get_nodes_that_are_reachable_from_pointed_ones_in_reversed_graph() -> None:
    # given
    execution_graph = nx.DiGraph()
    execution_graph.add_node("a", kind=INPUT_NODE_KIND)
    execution_graph.add_node("b", kind=INPUT_NODE_KIND)
    execution_graph.add_node("c", kind=STEP_NODE_KIND)
    execution_graph.add_node("d", kind=STEP_NODE_KIND)
    execution_graph.add_node("e", kind=OUTPUT_NODE_KIND)
    execution_graph.add_node("f", kind=OUTPUT_NODE_KIND)
    execution_graph.add_edge("a", "c")
    execution_graph.add_edge("b", "d")
    execution_graph.add_edge("c", "e")
    execution_graph.add_edge("d", "f")

    # when
    reachable_from_e = get_nodes_that_are_reachable_from_pointed_ones_in_reversed_graph(
        execution_graph=execution_graph, pointed_nodes={"e"}
    )
    reachable_from_f = get_nodes_that_are_reachable_from_pointed_ones_in_reversed_graph(
        execution_graph=execution_graph, pointed_nodes={"f"}
    )

    # then
    assert reachable_from_e == {
        "e",
        "c",
        "a",
    }, "Nodes a, c, e are reachable in reversed graph from e"
    assert reachable_from_f == {
        "f",
        "d",
        "b",
    }, "Nodes b, d, f are reachable in reversed graph from f"


def test_prepare_execution_graph_when_step_parameter_contains_undefined_reference() -> (
    None
):
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
            ],
            "steps": [
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_1",
                    "image": "$steps.step_2.crops",
                    "model_id": "vehicle-classification-eapcd/2",
                    "confidence": "$inputs.confidence",
                },
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "predictions",
                    "selector": "$steps.step_1.predictions",
                },
            ],
        }
    )

    # when
    with pytest.raises(SelectorToUndefinedNodeError):
        _ = prepare_execution_graph(deployment_spec=deployment_specs)


def test_prepare_execution_graph_when_graph_is_not_acyclic() -> None:
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
            ],
            "steps": [
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_1",
                    "image": "$steps.step_2.crops",
                    "model_id": "vehicle-classification-eapcd/2",
                },
                {
                    "type": "Crop",
                    "name": "step_2",
                    "image": "$inputs.image",
                    "detections": "$steps.step_1.predictions",
                },
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "crops",
                    "selector": "$steps.step_2.crops",
                },
            ],
        }
    )

    # when
    with pytest.raises(NotAcyclicGraphError):
        _ = prepare_execution_graph(deployment_spec=deployment_specs)


def test_prepare_execution_graph_when_graph_node_does_not_reach_output() -> None:
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
            ],
            "steps": [
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_1",
                    "image": "$inputs.image",
                    "model_id": "vehicle-classification-eapcd/2",
                },
                {
                    "type": "Crop",
                    "name": "step_2",
                    "image": "$inputs.image",
                    "detections": "$steps.step_1.predictions",
                },
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "predictions",
                    "selector": "$steps.step_1.predictions",
                },
            ],
        }
    )

    # when
    with pytest.raises(NodesNotReachingOutputError):
        _ = prepare_execution_graph(deployment_spec=deployment_specs)


def test_prepare_execution_graph_when_graph_when_there_is_a_collapse_of_condition_branch() -> (
    None
):
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
                {"type": "InferenceParameter", "name": "confidence"},
            ],
            "steps": [
                {
                    "type": "ClassificationModel",
                    "name": "step_1",
                    "image": "$inputs.image",
                    "model_id": "vehicle-classification-eapcd/2",
                    "confidence": "$inputs.confidence",
                },
                {
                    "type": "Condition",
                    "name": "step_2",
                    "left": "$steps.step_1.top",
                    "operator": "equal",
                    "right": "Car",
                    "step_if_true": "$steps.step_3",
                    "step_if_false": "$steps.step_4",
                },
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_3",
                    "image": "$inputs.image",
                    "model_id": "yolov8n-640",
                    "confidence": 0.5,
                    "iou_threshold": 0.4,
                },
                {
                    "type": "Crop",
                    "name": "step_4",
                    "image": "$inputs.image",
                    "detections": "$steps.step_3.predictions",
                },  # this step requires input from step_3 that will be executed conditionally in different branch
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "step_3_predictions",
                    "selector": "$steps.step_3.predictions",
                },
                {
                    "type": "JsonField",
                    "name": "step_4_crops",
                    "selector": "$steps.step_4.crops",
                },
            ],
        }
    )

    # when
    with pytest.raises(AmbiguousPathDetected):
        _ = prepare_execution_graph(deployment_spec=deployment_specs)


def test_prepare_execution_graph_when_graph_when_there_is_a_collapse_of_condition_branches() -> (
    None
):
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
                {"type": "InferenceParameter", "name": "confidence"},
            ],
            "steps": [
                {
                    "type": "ClassificationModel",
                    "name": "step_1",
                    "image": "$inputs.image",
                    "model_id": "vehicle-classification-eapcd/2",
                    "confidence": "$inputs.confidence",
                },
                {
                    "type": "Condition",
                    "name": "step_2",
                    "left": "$steps.step_1.top",
                    "operator": "equal",
                    "right": "Car",
                    "step_if_true": "$steps.step_4",
                    "step_if_false": "$steps.step_4",
                },
                {
                    "type": "Condition",
                    "name": "step_3",
                    "left": "$steps.step_1.top",
                    "operator": "equal",
                    "right": "Car",
                    "step_if_true": "$steps.step_4",
                    "step_if_false": "$steps.step_4",
                },
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_4",
                    "image": "$inputs.image",
                    "model_id": "yolov8n-640",
                    "confidence": 0.5,
                    "iou_threshold": 0.4,
                },
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "step_4_predictions",
                    "selector": "$steps.step_4.predictions",
                }
            ],
        }
    )

    # when
    with pytest.raises(AmbiguousPathDetected):
        _ = prepare_execution_graph(deployment_spec=deployment_specs)


def test_prepare_execution_graph_when_graph_when_steps_connection_make_the_graph_edge_incompatible_by_type() -> (
    None
):
    # given
    deployment_specs = DeploymentSpecV1.parse_obj(
        {
            "version": "1.0",
            "inputs": [
                {"type": "InferenceImage", "name": "image"},
            ],
            "steps": [
                {
                    "type": "ObjectDetectionModel",
                    "name": "step_1",
                    "image": "$inputs.image",
                    "model_id": "vehicle-classification-eapcd/2",
                },
                {
                    "type": "Crop",
                    "name": "step_2",
                    "image": "$steps.step_1.predictions",  # should be an image here
                    "detections": "$inputs.image",  # should be predictions here
                },
            ],
            "outputs": [
                {
                    "type": "JsonField",
                    "name": "crops",
                    "selector": "$steps.step_2.crops",
                },
            ],
        }
    )

    # when
    with pytest.raises(InvalidStepInputDetected):
        _ = prepare_execution_graph(deployment_spec=deployment_specs)
