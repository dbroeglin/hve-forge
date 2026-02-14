"""HVE Forge entry point."""

import typer

app = typer.Typer()


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    """HVE Forge CLI."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def hello() -> None:
    """Say hello to the world."""
    typer.echo("Hello World!")


def main() -> None:
    """Run the application."""
    app()


if __name__ == "__main__":
    main()
