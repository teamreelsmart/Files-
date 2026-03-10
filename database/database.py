import motor.motor_asyncio
from config import DB_URI, DB_NAME

dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
database = dbclient[DB_NAME]

user_data = database['users']

default_verify = {
    'is_verified': False,
    'verified_time': 0,
    'verify_token': "",
    'link': "",
    'service_token': "",
    'service_link': "",
    'token_created_at': 0,
    'warnings': 0,
    'is_banned': False,
}


def new_user(id):
    return {
        '_id': id,
        'verify_status': default_verify.copy(),
    }


async def present_user(user_id: int):
    found = await user_data.find_one({'_id': user_id})
    return bool(found)


async def add_user(user_id: int):
    user = new_user(user_id)
    await user_data.insert_one(user)
    return


async def db_verify_status(user_id):
    user = await user_data.find_one({'_id': user_id})
    if user:
        verify = default_verify.copy()
        verify.update(user.get('verify_status', {}))
        return verify
    return default_verify.copy()


async def db_update_verify_status(user_id, verify):
    await user_data.update_one({'_id': user_id}, {'$set': {'verify_status': verify}}, upsert=True)


async def db_find_user_by_service_token(token: str):
    user = await user_data.find_one({'verify_status.service_token': token})
    return user


async def full_userbase():
    user_docs = user_data.find()
    user_ids = [doc['_id'] async for doc in user_docs]
    return user_ids


async def del_user(user_id: int):
    await user_data.delete_one({'_id': user_id})
    return
