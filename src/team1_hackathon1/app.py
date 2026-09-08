from fastapi import FastAPI

app = FastAPI(
    title="team1-hackathon1",
    version="0.1.0",
    description="Tiny FastAPI service scaffolded for Dockerized deployment.",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "team1-hackathon1 is running"}


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "team1-hackathon1"}


def main() -> None:
    import uvicorn

    uvicorn.run("team1_hackathon1.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
