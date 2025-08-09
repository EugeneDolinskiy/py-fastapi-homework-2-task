from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from database.crud import create_movie, get_movie_by_id, patch_movie, delete_a_movie
from database.models import MovieModel
from schemas import MovieListResponseSchema, MovieDetailSchema, MovieUpdateRequest
from schemas.movies import MovieCreateDetailSchema, MovieItemSchema

router = APIRouter()


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(
        request: Request,
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(MovieModel).order_by(MovieModel.id.desc()).offset(offset).limit(per_page)
    )
    movies = result.scalars().all()

    total = await db.execute(select(func.count()).select_from(MovieModel))
    total_items = total.scalar_one()
    total_pages = (total_items + per_page - 1) // per_page

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    def build_url(p):
        return f"/theater/movies/?page={p}&per_page={per_page}"

    return {
        "movies": movies,
        "prev_page": build_url(page - 1) if page > 1 else None,
        "next_page": build_url(page + 1) if page < total_pages else None,
        "total_pages": total_pages,
        "total_items": total_items
    }


@router.get("/movies/{movie_id}/", response_model=MovieItemSchema)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await get_movie_by_id(db, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return movie


@router.post("/movies/", response_model=MovieDetailSchema, status_code=201)
async def add_movie(movie: MovieCreateDetailSchema, db: AsyncSession = Depends(get_db)):
    new_film = await create_movie(db, movie)
    return new_film


@router.patch("/movies/{movie_id}/")
async def update_movie(movie_data: MovieUpdateRequest, movie_id: int, db: AsyncSession = Depends(get_db)):
    current_movie = await get_movie_by_id(db, movie_id)
    if not current_movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    await patch_movie(db, movie_data, current_movie)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"detail": "Movie updated successfully."}
    )


@router.delete("/movies/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
    movie_to_delete = await get_movie_by_id(db, movie_id)
    if not movie_to_delete:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    await delete_a_movie(db, movie_to_delete)
