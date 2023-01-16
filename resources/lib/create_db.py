import sqlite3
from resources.lib.variables import *


def create_all():
    create_db_objects('videoCategories')
    create_db_objects('channel')
    create_db_objects('playlist')
    create_db_objects('playlistItems')
    create_db_objects('videos')
    create_db_objects('videos_custom')
    create_db_objects('last_update')
    create_db_objects('vwDiscoverMovies')
    create_db_objects('vwVideosAll')
    create_db_objects('vwVideosMovies')
    create_db_objects('vwVideosSeries')


def create_db_objects(table_name):
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Check if the table exists
    cursor.execute("PRAGMA table_info(" + table_name + ")")
    result = cursor.fetchall()
    if result:
        # The table exists so exit
        conn.close()
        return ()

    if table_name == 'videoCategories':
        cursor.execute('''CREATE TABLE videoCategories (
                            id text,
                            channel_id text,
                            title text,
                            assignable boolean,
                            PRIMARY KEY(id, channel_id)
                        )''')

    if table_name == "channel":
        cursor.execute("""CREATE TABLE channel (
                            id text,
                            title text,
                            description text,
                            custom_url text,
                            published_at datetime,
                            thumb_url text,
                            country text,
                            default_language text,
                            uploads_playlist_id text,
                            video_count integer,
                            topic_ids text,
                            topic_categories text,
                            privacy_status text,
                            keywords text,
                            unsubscribed_trailer text,
                            media_type text,
                            disable_update text,
                            discovered integer,
                            removed integer,
                            PRIMARY KEY (id)
                        )""")

    if table_name == "playlist":
        cursor.execute('''CREATE TABLE playlist (
                            id text, 
                            published_at datetime,
                            channel_id text, 
                            title text,
                            description text, 
                            channel_title text, 
                            default_language text, 
                            thumbnail_url text, 
                            thumbnail_width integer, 
                            thumbnail_height integer, 
                            privacy_status text, 
                            item_count integer, 
                            local_title text,
                            local_description text
                            media_type text,
                            sort_by text,
                            disable_update text,
                            PRIMARY KEY(id)
                        )''')

    if table_name == "playlistItems":
        cursor.execute('''CREATE TABLE playlistItems (
                            id text,
                            playlist_id text,
                            position integer,
                            published_at datetime,
                            channel_id text,
                            channel_title text,
                            video_title text,
                            video_description text,
                            thumbnail_url text,
                            thumbnail_width integer,
                            thumbnail_height integer,
                            video_owner_channel_title text,
                            video_owner_channel_id text,
                            video_id text,
                            video_published_at datetime,
                            privacy_status text,
                            PRIMARY KEY (id)
                        )''')

    if table_name == "videos":
        cursor.execute('''CREATE TABLE videos (
                            id text,
                            published_at datetime,
                            channel_id text,
                            title text,
                            description text,
                            thumbnail_url text,
                            thumbnail_width integer,
                            thumbnail_height integer,
                            channel_title text,
                            tags text,
                            category_id text,
                            default_audio_language text,
                            duration int,
                            definition text,
                            caption text,
                            licensed_content boolean,
                            region_allowed text,
                            region_blocked text,
                            PRIMARY KEY(id)
                        )''')

    if table_name == "videos_custom":
        cursor.execute('''CREATE TABLE videos_custom (
                            video_id text,
                            clean_title text,
                            kodi_files boolean,
                            season integer,
                            episode integer,
                            PRIMARY KEY(video_id)
                        )''')

    if table_name == 'last_update':
        cursor.execute('''CREATE TABLE "last_update" (
                            series	integer,
                            movies	integer,
                            music	integer
                        )''')
        cursor.execute('''insert into last_update VALUES ('1970-01-01', '1970-01-01', '1970-01-01')''')

    if table_name == 'vwDiscoverMovies':
        cursor.execute('''CREATE VIEW vwDiscoverMovies AS
                            select	pi.video_owner_channel_id, pi.video_owner_channel_title, count(*) 'count'
                            from playlistItems pi
                            inner join playlist p on pi.playlist_id = p.id and p.media_type = 'movies'
                            where video_owner_channel_id not in (select id from channel)
                            and video_owner_channel_id <> 'UCuVPpxrm2VAgpH3Ktln4HXg'
                            group by pi.video_owner_channel_id, pi.video_owner_channel_title
                            having count(*) > 1
                            order by 3 desc
                        ''')

    if table_name == 'vwVideosAll':
        cursor.execute('''CREATE VIEW vwVideosAll AS
                            select	case when pi.playlist_id in (select id from playlist) 
                                        then pi.playlist_id 
                                        else pi.channel_id 
                                end src_playlist,
                                case when pi.playlist_id in (select id from playlist) 
                                        then 'playlist' 
                                        else 'channel' 
                                end channel_type,
                                ifnull(c.media_type, p.media_type) media_type,
                                v.id as video_id,
                                v.published_at,
                                v.title,
                                vc.clean_title,
                                v.description,
                                v.region_allowed,
                                v.region_blocked,
                                vc.season,
                                vc.episode,
                                vc.kodi_files
                            from videos v
                            left join videos_custom vc on v.id = vc.video_id
                            left join playlistItems pi on v.id = pi.video_id
                            left join channel c on pi.channel_id = c.id
                            left join playlist p on pi.playlist_id = p.id
                        ''')

    if table_name == 'vwVideosMovies':
        cursor.execute('''CREATE VIEW vwVideosMovies AS
                            select 	case when pi.playlist_id in (select id from playlist) 
                                        then pi.playlist_id 
                                        else pi.channel_id 
                                    end src_playlist,
                                    case when pi.playlist_id in (select id from playlist) 
                                        then 'playlist' 
                                        else 'channel' 
                                    end channel_type,
                                    v.id as video_id,
                                    v.published_at,
                                    v.title,
                                    vc.clean_title,
                                    v.region_allowed,
                                    v.region_blocked,
                                    vc.kodi_files
                            from videos v
                            inner join playlistItems pi on v.id = pi.video_id
                            inner join videos_custom vc on v.id = vc.video_id
                            left join channel c on pi.channel_id = c.id
                            left join playlist p on pi.playlist_id = p.id
                            where coalesce(c.media_type, p.media_type) = 'movies'
                        ''')

    if table_name == 'vwVideosSeries':
        cursor.execute('''CREATE VIEW vwVideosSeries AS
                            select	case when pi.playlist_id in (select id from playlist) 
                                        then pi.playlist_id 
                                        else pi.channel_id 
                                    end src_playlist,
                                    case when pi.playlist_id in (select id from playlist) 
                                        then 'playlist' 
                                        else 'channel'
                                    end channel_type,
                                    case when p.sort_by is not null 
                                        then pi.position 
                                    end position,
                                    pi.published_at as pl_published_at,
                                    pi.channel_title,
                                    v.id as video_id,
                                    v.published_at,
                                    v.title,
                                    vc.clean_title,
                                    v.description,
                                    v.duration,
                                    v.thumbnail_url,
                                    vc.season,
                                    vc.episode,
                                    vc.kodi_files
                            from videos v
                            inner join playlistItems pi on v.id = pi.video_id
                            left join videos_custom vc on v.id = vc.video_id
                            left join channel c on pi.channel_id = c.id
                            left join playlist p on pi.playlist_id = p.id
                            where coalesce(c.media_type, p.media_type) = 'series'
                        ''')

    # Save the changes and close the connection
    conn.commit()
    conn.close()


def compact_db():
    # Connect to the database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Execute the VACUUM command
    __logger("Compacting database")
    cursor.execute("VACUUM")
    conn.commit()
    __logger("Compacting complete")

    # Close the cursor and connection
    cursor.close()
    conn.close()