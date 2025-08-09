from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import MovieModel, GenreModel, ActorModel, LanguageModel, CountryModel
from schemas import MovieDetailSchema, MovieUpdateRequest


async def get_movie_by_id(db: AsyncSession, movie_id: int) -> MovieModel | None:
    # preload all relationships for later data serialization
    stmt = select(MovieModel).options(
        selectinload(MovieModel.genres),
        selectinload(MovieModel.actors),
        selectinload(MovieModel.languages),
        selectinload(MovieModel.country),
    ).where(MovieModel.id == movie_id)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create(db: AsyncSession, model, attr_name: str, value: str):
    stmt = select(model).where(getattr(model, attr_name) == value)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()

    if not obj:
        obj = model(**{attr_name: value})
        db.add(obj)
        await db.flush()

    return obj


async def populate_relationship(db: AsyncSession, movie: dict, key: str, model, attr_name: str):
    if not movie.get(key):
        return
    items = []
    for item_value in movie[key]:
        obj = await get_or_create(db, model, attr_name, item_value)
        items.append(obj)
    movie[key] = items


async def populate_country(db: AsyncSession, movie: dict):
    if not movie.get("country"):
        return
    country_code = movie["country"].upper()
    country = await get_or_create(db, CountryModel, "code", country_code)
    movie["country"] = country


async def create_movie(db: AsyncSession, movie: MovieDetailSchema) -> MovieModel:
    new_movie = movie.model_dump()

    await populate_relationship(db, new_movie, "genres", GenreModel, "name")
    await populate_relationship(db, new_movie, "actors", ActorModel, "name")
    await populate_relationship(db, new_movie, "languages", LanguageModel, "name")
    await populate_country(db, new_movie)

    new_movie_obj = MovieModel(**new_movie)
    db.add(new_movie_obj)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()

        # Optional: narrow the error to unique constraint on name+date
        if "unique constraint" in str(e.orig).lower() or 'duplicate key' in str(e.orig).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A movie with the name '{movie.name}' and release date '{movie.date}' already exists."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create movie due to a database integrity error."
            )
    await db.refresh(new_movie_obj)

    return await get_movie_by_id(db, new_movie_obj.id)


async def patch_movie(db: AsyncSession, update_data: MovieUpdateRequest, current_movie: MovieModel):
    for key, value in update_data.model_dump(exclude_none=True).items():
        setattr(current_movie, key, value)
    await db.commit()
    await db.refresh(current_movie)
    return current_movie


async def delete_a_movie(db: AsyncSession, movie):
    await db.delete(movie)
    await db.commit()
