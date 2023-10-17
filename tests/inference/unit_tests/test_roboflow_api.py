from typing import Type
from unittest import mock
from unittest.mock import MagicMock

import pytest
import requests.exceptions
from requests_mock import Mocker

from inference.core.env import API_BASE_URL
from inference.core.exceptions import (
    MalformedRoboflowAPIResponseError,
    WorkspaceLoadError,
    DatasetLoadError,
    MissingDefaultModelError,
)
from inference.core import roboflow_api
from inference.core.roboflow_api import (
    wrap_roboflow_api_errors,
    raise_from_lambda,
    get_roboflow_workspace,
    get_roboflow_dataset_type,
    get_roboflow_model_type,
)
from inference.core.utils.url_utils import wrap_url


class TestException1(Exception):
    pass


class TestException2(Exception):
    pass


def test_wrap_roboflow_api_errors_when_no_error_occurs() -> None:
    # given

    @wrap_roboflow_api_errors(
        on_connection_error=lambda e: raise_from_lambda(e, TestException1, "some"),
        on_http_error=lambda e: raise_from_lambda(e, TestException2, "other"),
    )
    def my_fun(a: int, b: int) -> int:
        return a + b

    # when
    result = my_fun(2, 3)

    # then
    assert result == 5


@pytest.mark.parametrize(
    "exception_class", [ConnectionError, requests.exceptions.ConnectionError]
)
def test_wrap_roboflow_api_errors_when_connection_error_occurs(
    exception_class: Type[Exception],
) -> None:
    @wrap_roboflow_api_errors(
        on_connection_error=lambda e: raise_from_lambda(e, TestException1, "some"),
        on_http_error=lambda e: raise_from_lambda(e, TestException2, "other"),
    )
    def my_fun(a: int, b: int) -> int:
        raise exception_class("some")

    # when
    with pytest.raises(TestException1):
        _ = my_fun(2, 3)


def test_wrap_roboflow_api_errors_when_connection_http_error_occurs() -> None:
    @wrap_roboflow_api_errors(
        on_connection_error=lambda e: raise_from_lambda(e, TestException1, "some"),
        on_http_error=lambda e: raise_from_lambda(e, TestException2, "other"),
    )
    def my_fun(a: int, b: int) -> int:
        raise requests.exceptions.HTTPError("some")

    # when
    with pytest.raises(TestException2):
        _ = my_fun(2, 3)


def test_wrap_roboflow_api_errors_when_connection_json_parsing_error_occurs() -> None:
    @wrap_roboflow_api_errors(
        on_connection_error=lambda e: raise_from_lambda(e, TestException1, "some"),
        on_http_error=lambda e: raise_from_lambda(e, TestException2, "other"),
    )
    def my_fun(a: int, b: int) -> int:
        raise requests.exceptions.InvalidJSONError("some")

    # when
    with pytest.raises(MalformedRoboflowAPIResponseError):
        _ = my_fun(2, 3)


def test_get_roboflow_workspace_when_http_error_occurs(requests_mock: Mocker) -> None:
    # given
    requests_mock.get(
        url=wrap_url(f"{API_BASE_URL}/"),
        status_code=403,
    )

    # when
    with pytest.raises(WorkspaceLoadError):
        _ = get_roboflow_workspace(api_key="my_api_key")

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key"


@mock.patch.object(roboflow_api.requests, "get")
def test_get_roboflow_workspace_when_connection_error_occurs(
    get_mock: MagicMock,
) -> None:
    # given
    get_mock.side_effect = ConnectionError()

    # when
    with pytest.raises(WorkspaceLoadError):
        _ = get_roboflow_workspace(api_key="my_api_key")


def test_get_roboflow_workspace_when_response_parsing_error_occurs(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(f"{API_BASE_URL}/"),
        content=b"For sure not a JSON payload",
    )

    # when
    with pytest.raises(MalformedRoboflowAPIResponseError):
        _ = get_roboflow_workspace(api_key="my_api_key")

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key"


def test_get_roboflow_workspace_when_workspace_id_is_empty(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(f"{API_BASE_URL}/"),
        json={"some": "payload"},
    )

    # when
    with pytest.raises(WorkspaceLoadError):
        _ = get_roboflow_workspace(api_key="my_api_key")

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key"


def test_get_roboflow_workspace_when_response_is_valid(requests_mock: Mocker) -> None:
    # given
    requests_mock.get(
        url=wrap_url(f"{API_BASE_URL}/"),
        json={"workspace": "my_workspace"},
    )

    # when
    result = get_roboflow_workspace(api_key="my_api_key")

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key"
    assert result == "my_workspace"


def test_get_roboflow_dataset_type_when_http_error_occurs(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/?api_key=my_api_key&nocache=true"
        ),
        status_code=403,
    )

    # when
    with pytest.raises(DatasetLoadError):
        _ = get_roboflow_dataset_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
        )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"


@mock.patch.object(roboflow_api.requests, "get")
def test_get_roboflow_dataset_type_when_connection_error_occurs(
    get_mock: MagicMock,
) -> None:
    # given
    get_mock.side_effect = ConnectionError()

    # when
    with pytest.raises(DatasetLoadError):
        _ = get_roboflow_dataset_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
        )


def test_get_roboflow_dataset_type_when_response_parsing_error_occurs(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/?api_key=my_api_key&nocache=true"
        ),
        content=b"For sure not a JSON payload",
    )

    # when
    with pytest.raises(MalformedRoboflowAPIResponseError):
        _ = get_roboflow_dataset_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
        )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"


def test_get_roboflow_dataset_type_when_project_is_empty(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/?api_key=my_api_key&nocache=true"
        ),
        json={"project": {}},
    )

    # when
    result = get_roboflow_dataset_type(
        api_key="my_api_key", workspace_id="my_workspace", dataset_id="coins_detection"
    )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"
    assert result == "object-detection"


def test_get_roboflow_dataset_type_when_response_is_valid(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/?api_key=my_api_key&nocache=true"
        ),
        json={"project": {"type": "classification"}},
    )

    # when
    result = get_roboflow_dataset_type(
        api_key="my_api_key", workspace_id="my_workspace", dataset_id="coins_detection"
    )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"
    assert result == "classification"


def test_get_roboflow_model_type_when_http_error_occurs(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/1/?api_key=my_api_key&nocache=true"
        ),
        status_code=403,
    )

    # when
    with pytest.raises(DatasetLoadError):
        _ = get_roboflow_model_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
            version_id="1",
            project_task_type="object-detection",
        )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"


@mock.patch.object(roboflow_api.requests, "get")
def test_get_roboflow_model_type_when_connection_error_occurs(
    get_mock: MagicMock,
) -> None:
    # given
    get_mock.side_effect = ConnectionError()

    # when
    with pytest.raises(DatasetLoadError):
        _ = get_roboflow_model_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
            version_id="1",
            project_task_type="object-detection",
        )


def test_get_roboflow_model_type_when_response_parsing_error_occurs(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/1/?api_key=my_api_key&nocache=true"
        ),
        content=b"For sure not a JSON payload",
    )

    # when
    with pytest.raises(MalformedRoboflowAPIResponseError):
        _ = get_roboflow_model_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
            version_id="1",
            project_task_type="object-detection",
        )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"


def test_get_roboflow_model_type_when_default_model_can_be_chosen(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/1/?api_key=my_api_key&nocache=true"
        ),
        json={"version": {}},
    )

    # when
    result = get_roboflow_model_type(
        api_key="my_api_key",
        workspace_id="my_workspace",
        dataset_id="coins_detection",
        version_id="1",
        project_task_type="object-detection",
    )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"
    assert result == "yolov5v2s"


def test_get_roboflow_model_type_when_default_model_cannot_be_chosen(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/1/?api_key=my_api_key&nocache=true"
        ),
        json={"version": {}},
    )

    # when
    with pytest.raises(MissingDefaultModelError):
        _ = get_roboflow_model_type(
            api_key="my_api_key",
            workspace_id="my_workspace",
            dataset_id="coins_detection",
            version_id="1",
            project_task_type="unknown",
        )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"


def test_get_roboflow_model_type_when_response_is_valid(
    requests_mock: Mocker,
) -> None:
    # given
    requests_mock.get(
        url=wrap_url(
            f"{API_BASE_URL}/my_workspace/coins_detection/1/?api_key=my_api_key&nocache=true"
        ),
        json={"version": {"modelType": "yolov8n"}},
    )

    # when
    result = get_roboflow_model_type(
        api_key="my_api_key",
        workspace_id="my_workspace",
        dataset_id="coins_detection",
        version_id="1",
        project_task_type="object-detection",
    )

    # then
    assert requests_mock.last_request.query == "api_key=my_api_key&nocache=true"
    assert result == "yolov8n"
