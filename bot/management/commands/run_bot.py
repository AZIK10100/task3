# bot/management/commands/run_bot.py

import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher
from bot.login import login_router
from bot.card import card_router

class Command(BaseCommand):
    help = "Telegram botni ishga tushirish"

    def handle(self, *args, **options):
        async def main():
            bot = Bot(token=settings.BOT_TOKEN)
            dp = Dispatcher()

            dp.include_routers(login_router, card_router)

            self.stdout.write(self.style.SUCCESS("Bot ishga tushdi..."))
            await dp.start_polling(bot)

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Bot to'xtatildi"))
