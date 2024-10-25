from aiogram import F, types, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.functions import check_link, check_limit, add_group, get_group_ids, remove_group
from db.database import db
from keyboards.inline import inline_keyboard

router = Router()

class AddingGroup(StatesGroup):
    add_group = State()


@router.message(Command("authorize"))
async def auth(msg: types.Message):
    async with db.transaction():
        db.status("UPDATE users SET status = 'in progress' WHERE user_id = $2", msg.from_user.id) 
    await msg.answer("Нажмите кнопку ниже, чтобы перейти на страницу аутентификации:", reply_markup=inline_keyboard)


@router.message(Command("updates_on"))
async def turn_off_updates(msg: types.Message):
    async with db.transaction():
        await db.status("UPDATE users SET updates = TRUE WHERE user_id = $1", msg.from_user.id)
    await msg.answer("Вы успешно включили уведомления о новых постах!")


@router.message(Command("updates_off"))
async def turn_off_updates(msg: types.Message):
    async with db.transaction():
        await db.status("UPDATE users SET updates = FALSE WHERE user_id = $1", msg.from_user.id)
    await msg.answer("Вы успешно отключили уведомления о новых постах!")


@router.message(Command("add_group"))
async def set_add_group(msg: types.Message, state: FSMContext):
    await state.set_state(AddingGroup.add_group)
    await msg.answer("Введите ссылку на группу: ")


@router.message(AddingGroup.add_group, Command("stop"))
async def stop_getting_link(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Вы отменили ввод!") 


@router.message(AddingGroup.add_group, F.text)
async def accept_link(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    link = msg.text.strip()

    correct_link = await check_link(link, msg.from_user.id)
    limit = await check_limit(user_id)

    if not correct_link and not limit:
        await msg.answer(
            "Вы ввели некорректную ссылку, а также исчерпали свой лимит на добавление групп! "
            "Приобретите подписку!"
        )
        return

    if not correct_link:
        await msg.answer("Вы ввели некорректную ссылку!")
        return

    if not limit:
        await msg.answer(
            "Вы достигли лимита! Больше групп добавить не получится. "
            "Оформите подписку, чтобы увеличить количество групп."
        )
        await state.clear()
        return

    result = await add_group(user_id, link)
    if result:
        await msg.answer(
            "Вы успешно добавили группу! Если хотите продолжить, введите ещё одну ссылку, или нажмите /stop."
        )
    else:
        await msg.answer("Произошла неизвестная ошибка. Обратитесь к администратору или попробуйте позднее.")


@router.message(AddingGroup.add_group, ~F.text)
async def got_not_link(msg: types.Message):
    await msg.answer("Введите, ссылку, пожалуйста. Если хотите прекратить,  нажмите /stop") 


@router.message(Command("remove_group"))
async def delete_group(msg: types.Message):
    await msg.answer("Введите ссылку на группу, которую хотите удалить: ")

    result = await remove_group(msg.from_user.id, msg.text.strip())

    if result:
        await msg.answer("Вы успешно удалили группу!")

    else:   
        await msg.answer("Произошла неизвестная ошибка. Обратитесь к администратору или попробуйте позднее.")


@router.message(Command("get_group_list"))
async def get_groups(msg: types.Message):
    groups = await get_group_ids(msg.from_user.id)
    groups = [str(group) for group in groups]

    if not groups:
        await msg.answer("Произошла ошибка при получении списка групп!")
    else:
        await msg.answer("Ваши группы:\n" + "\n".join(groups))