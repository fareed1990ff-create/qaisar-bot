import os, json, random, urllib.request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
