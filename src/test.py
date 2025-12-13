# test_new_user.py
import requests
import asyncio
import websockets
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_new_user():
    """Тест с новым пользователем"""

    print("🧪 Тестирование нового пользователя")
    print("=" * 50)

    # 1. Создаем нового пользователя
    print("1. Регистрируем нового пользователя...")
    new_user = {
        "email": f"test_{int(time.time())}@mail.com",
        "username": f"TestUser_{int(time.time())}",
        "password": "123456"
    }

    response = requests.post("http://localhost:8000/auth/register", json=new_user)

    if response.status_code != 201:
        print(f"❌ Ошибка регистрации: {response.text}")
        return

    token = response.json()["access_token"]
    user_id = response.json()["user_id"]

    print(f"✅ Пользователь создан: id={user_id}, username={new_user['username']}")

    # 2. Проверяем есть ли запись в user_status ДО подключения
    from src.database.connection import SessionLocal
    from src.models.user_status import UserStatus

    db = SessionLocal()
    status_before = db.query(UserStatus).filter(UserStatus.user_id == user_id).first()
    db.close()

    if status_before:
        print(f"⚠️  Запись уже существует ДО подключения: status={status_before.status}")
    else:
        print(f"✅ Записи нет ДО подключения (как и должно быть)")

    # 3. Подключаемся через WebSocket
    print("\n2. Подключаемся через WebSocket...")

    try:
        async with websockets.connect(f"ws://localhost:8000/ws?token={token}") as ws:
            print("✅ WebSocket подключен")

            # Получаем приветствие
            response = await ws.recv()
            print(f"📥 Сервер: {response}")

            # Ждем 2 секунды
            await asyncio.sleep(2)

            # Проверяем появилась ли запись ПОСЛЕ подключения
            db = SessionLocal()
            status_after = db.query(UserStatus).filter(UserStatus.user_id == user_id).first()
            db.close()

            if status_after:
                print(f"✅ Запись появилась ПОСЛЕ подключения!")
                print(f"   user_id={status_after.user_id}")
                print(f"   status={status_after.status}")
                print(f"   last_seen={status_after.last_seen}")
            else:
                print(f"❌ Запись НЕ появилась ПОСЛЕ подключения!")

            # Отправляем ping
            await ws.send(json.dumps({"type": "ping"}))
            pong = await ws.recv()
            print(f"📥 Pong: {pong}")

    except Exception as e:
        print(f"❌ Ошибка WebSocket: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 50)
    print("Тест завершен")


if __name__ == "__main__":
    import time

    asyncio.run(test_new_user())