import typer
from typing_extensions import Annotated

import inference_cli.lib
from inference_cli.server import server_app
from inference_cli.cloud import cloud_app

app = typer.Typer()

app.add_typer(server_app, name="server")
app.add_typer(cloud_app, name="cloud")


@app.command()
def infer(
    image: Annotated[
        str, typer.Argument(help="URL or local path of image to run inference on.")
    ],
    project_id: Annotated[
        str,
        typer.Option(
            "--project-id", "-p", help="Roboflow project to run inference with."
        ),
    ],
    model_version: Annotated[
        str,
        typer.Option(
            "--model-version",
            "-v",
            help="Version of model to run inference with.",
        ),
    ],
    api_key: Annotated[
        str,
        typer.Option("--api-key", "-a", help="Roboflow API key for your workspace."),
    ],
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to run inference on."),
    ] = "http://localhost:9001",
):
    typer.echo(
        f"Running inference on image {image}, using model ({project_id}/{model_version}), and host ({host})"
    )
    inference_cli.lib.infer(image, project_id, model_version, api_key, host)


if __name__ == "__main__":
    app()
