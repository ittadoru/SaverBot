docker compose down
docker volume rm pgdata
docker compose run --rm bot bash
alembic revision --autogenerate -m "init"
exit
docker compose up --build