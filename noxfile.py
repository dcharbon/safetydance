import nox_poetry as nox


@nox.session(python=["3.8", "3.9", "3.10", "3.11",])
def test(session):
    session.install('pytest', '.')
    session.install('pytest-cov', '.')
    session.run('pytest')
