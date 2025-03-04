from typing import Annotated, List, Literal, Union

from pydantic import BaseModel, Field

from inference.enterprise.deployments.entities.inputs import (
    InferenceImage,
    InferenceParameter,
)
from inference.enterprise.deployments.entities.outputs import JsonField
from inference.enterprise.deployments.entities.steps import (
    AbsoluteStaticCrop,
    ClassificationModel,
    ClipComparison,
    Condition,
    Crop,
    DetectionFilter,
    DetectionOffset,
    InstanceSegmentationModel,
    KeypointsDetectionModel,
    MultiLabelClassificationModel,
    ObjectDetectionModel,
    OCRModel,
    RelativeStaticCrop,
)

InputType = Annotated[
    Union[InferenceImage, InferenceParameter], Field(discriminator="type")
]
StepType = Annotated[
    Union[
        ClassificationModel,
        MultiLabelClassificationModel,
        ObjectDetectionModel,
        KeypointsDetectionModel,
        InstanceSegmentationModel,
        OCRModel,
        Crop,
        Condition,
        DetectionFilter,
        DetectionOffset,
        ClipComparison,
        RelativeStaticCrop,
        AbsoluteStaticCrop,
    ],
    Field(discriminator="type"),
]


class DeploymentSpecV1(BaseModel):
    version: Literal["1.0"]
    inputs: List[InputType]
    steps: List[StepType]
    outputs: List[JsonField]


class DeploymentSpecification(BaseModel):
    specification: DeploymentSpecV1  # in the future - union with discriminator can be used
