"""Truth Core CLI."""
import click

@click.group()
def cli():
    """Truth Core CLI."""
    pass

@cli.command()
@click.option('--inputs', '-i', required=True)
@click.option('--profile', '-p', default='base')
@click.option('--out', '-o', required=True)
def judge(inputs, profile, out):
    """Run readiness check."""
    click.echo(f"Running judge: inputs={inputs}, profile={profile}, out={out}")

@cli.command()
@click.option('--inputs', '-i', required=True)
@click.option('--out', '-o', required=True)
def recon(inputs, out):
    """Run reconciliation."""
    click.echo(f"Running recon: inputs={inputs}, out={out}")

@cli.command()
@click.option('--inputs', '-i', required=True)
@click.option('--fsm', '-f', required=True)
@click.option('--out', '-o', required=True)
def trace(inputs, fsm, out):
    """Run trace analysis."""
    click.echo(f"Running trace: inputs={inputs}, fsm={fsm}, out={out}")

@cli.command()
@click.option('--inputs', '-i', required=True)
@click.option('--out', '-o', required=True)
def index(inputs, out):
    """Run knowledge indexing."""
    click.echo(f"Running index: inputs={inputs}, out={out}")

@cli.command()
@click.option('--inputs', '-i', required=True)
@click.option('--mode', '-m', required=True)
@click.option('--out', '-o', required=True)
def intel(inputs, mode, out):
    """Run intelligence analysis."""
    click.echo(f"Running intel: inputs={inputs}, mode={mode}, out={out}")

def main():
    cli()

if __name__ == '__main__':
    main()
