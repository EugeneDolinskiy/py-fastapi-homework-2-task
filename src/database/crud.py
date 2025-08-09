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


async def populate_genres(db: AsyncSession, movie: dict):
    if not movie["genres"]:
        return
    genres = []
    for genre in movie["genres"]:
        genre = await get_or_create_genre(db, genre)
        print(f"{genre.id=}")
        genres.append(genre)
    movie["genres"] = genres


async def populate_actors(db: AsyncSession, movie: dict):
    if not movie["actors"]:
        return
    actors = []
    for actor in movie["actors"]:
        actor = await get_or_create_actor(db, actor)
        print(f"{actor.id=}")
        actors.append(actor)
    movie["actors"] = actors


async def populate_languages(db: AsyncSession, movie: dict):
    if not movie["languages"]:
        return
    languages = []
    for language in movie["languages"]:
        language = await get_or_create_language(db, language)
        print(f"{language.id=}")
        languages.append(language)
    movie["languages"] = languages


async def populate_country(db: AsyncSession, movie: dict):
    if not movie["country"]:
        return
    country = await get_or_create_country(db, movie["country"])
    print(f"{country.id=}")
    movie["country"] = country


async def create_movie(db: AsyncSession, movie: MovieDetailSchema) -> MovieModel:
    print("create_movie")

    new_movie = movie.model_dump()

    await populate_genres(db, new_movie)
    await populate_actors(db, new_movie)
    await populate_languages(db, new_movie)
    await populate_country(db, new_movie)

    new_movie = MovieModel(**new_movie)
    db.add(new_movie)
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
    await db.refresh(new_movie)

    return await get_movie_by_id(db, new_movie.id)


async def get_movies(db: AsyncSession):
    result = await db.execute(select(MovieModel))
    movies = result.scalars().all()
    return movies


async def get_movie(db: AsyncSession, movie_id: int):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    return movie


async def patch_movie(db: AsyncSession, update_data: MovieUpdateRequest, current_movie: MovieModel):
    for key, value in update_data.model_dump(exclude_none=True).items():
        setattr(current_movie, key, value)
    await db.commit()
    await db.refresh(current_movie)
    return current_movie


async def delete_a_movie(db: AsyncSession, movie):
    await db.delete(movie)
    await db.commit()


async def get_or_create_genre(db: AsyncSession, genre_name: str) -> GenreModel:
    result = await db.execute(select(GenreModel).where(GenreModel.name == genre_name))
    genre_obj = result.scalar_one_or_none()

    if not genre_obj:
        genre_obj = GenreModel(name=genre_name)
        db.add(genre_obj)
        await db.flush()

    return genre_obj


async def get_or_create_actor(db: AsyncSession, actor_name: str) -> ActorModel:
    result = await db.execute(select(ActorModel).where(ActorModel.name == actor_name))
    actor_obj = result.scalar_one_or_none()

    if not actor_obj:
        actor_obj = ActorModel(name=actor_name)
        db.add(actor_obj)
        await db.flush()

    return actor_obj


async def get_or_create_language(db: AsyncSession, language: str) -> LanguageModel:
    result = await db.execute(select(LanguageModel).where(LanguageModel.name == language))
    language_obj = result.scalar_one_or_none()

    if not language_obj:
        language_obj = LanguageModel(name=language)
        db.add(language_obj)
        await db.flush()

    return language_obj


async def get_or_create_country(db: AsyncSession, country_code: str) -> CountryModel:
    result = await db.execute(select(CountryModel).where(CountryModel.code == country_code))
    country_obj = result.scalar_one_or_none()

    if not country_obj:
        country_obj = CountryModel(code=country_code.upper())
        db.add(country_obj)
        await db.flush()

    return country_obj
