from aiogram import F, types, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.functions import check_link, check_limit, add_group
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db.connection_manager import get_db_connection

router = Router()

class AddingGroup(StatesGroup):
    add_group = State()

@router.message(Command("/authorize"))
async def auth(msg: types.Message):
    button = InlineKeyboardButton(text="Перейти на сайт", url="http://localhost:8000/login")
    keyboard = InlineKeyboardMarkup().add(button)
    async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):
            pass 
    await msg.answer("Нажмите кнопку ниже, чтобы перейти на страницу аутентификации:", reply_markup=keyboard)

@router.message(Command("add_group"))
async def set_add_group(msg: types.Message, state: FSMContext):
    await state.set_state(AddingGroup.add_group)
    await msg.answer("Введите ссылку на группу: ")

@router.message(AddingGroup.add_group, Command("stop"))
async def stop_getting_link(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Вы отменили ввод!") 


@router.message(AddingGroup.add_group, F.text)
async def accept_link(msg: types.Message):
    correct_link = await check_link(msg.text.strip())
    limit = await check_limit(msg.from_user.id)
    if correct_link and limit:
        result = await add_group(msg.from_user.id, msg.text.strip())
        if result:
            await msg.answer("Вы успешно добавили группу! Если хотите продолжить, введите ещё одну ссылку, или нажмите /stop")
        else:
            await msg.answer("Произошла неизвестная ошибка. Обратитесь к администратору или попробуйте позднее.")
    elif not limit and correct_link:
        await msg.answer("Вы достигли лимита! Больше групп добавить не получиться( Оформите подписку, чтобы увеличить количество групп")
    elif limit and not correct_link:
        await msg.answer("Вы ввели некорректную ссылку!")
    else:
        await msg.answer("Вы ввели некорректную ссылку, а также исчерпали свой лимит на добавление групп! Приобретите подписку!")


@router.message(AddingGroup.add_group, ~F.text)
async def got_not_link(msg: types.Message):
    await msg.answer("Введите, ссылку, пожалуйста. Если хотите прекратить,  нажмите /stop") 
