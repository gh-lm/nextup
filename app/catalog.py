"""Every lookup goes to TheTVDB."""
from . import tvdb
from .tvdb import TvdbError

def search_multi(query, page=1):
    return tvdb.search_multi(query, page=page)

def show(show_id):
    return tvdb.show(show_id)

def show_detail(show_id):
    return tvdb.show_detail(show_id)

def movie(movie_id):
    return tvdb.movie(movie_id)

def movie_detail(movie_id):
    return tvdb.movie_detail(movie_id)

def season(show_id, season_number):
    return tvdb.season(show_id, season_number)

def episode(show_id, season_number, episode_number):
    return tvdb.episode(show_id, season_number, episode_number)
