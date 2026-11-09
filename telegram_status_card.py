"""Locally rendered Telegram status cards; never include paths or credentials."""
import io
from PIL import Image, ImageDraw, ImageFont


def fields(status, uptime):
    try:
        count = max(0, int(status.get('total_files', 0)))
    except (ValueError, TypeError, OverflowError):
        count = 0
    seconds = max(0, int(uptime))
    return {
        'count': f'{count:,}'.replace(',', '.'),
        'storage': {'smb': 'SMB', 'local': 'Lokal'}.get(str(status.get('storage', '')).lower(), 'Unbekannt'),
        'index': 'Wird aufgebaut' if status.get('building') else 'Ruhend',
        'uptime': f'{seconds // 3600} h {seconds % 3600 // 60} min',
    }


def caption(status, uptime, now, daily=False):
    values = fields(status, uptime)
    index = '🟡 Wird aufgebaut' if status.get('building') else '⚪ Ruhend'
    heading = '🌙 <b>MP3z · Tagesstatus 22:00</b>\n📊 Aktueller Bibliotheksstatus' if daily else '🎧 <b>MP3z ist gestartet</b>\n🟢 <b>HTTP bereit</b>'
    return (f'{heading}\n\n'
            f'🎵 Titel im Index: <b>{values["count"]}</b>\n'
            f'💾 Speicher: {values["storage"]}\n'
            f'📚 Index: {index}\n'
            f'⏱ Laufzeit: {values["uptime"]}\n\n'
            f'🕒 {now:%d.%m.%Y · %H:%M %Z}')


def render(status, uptime, now, daily=False):
    values = fields(status, uptime)
    image = Image.new('RGB', (1000, 580), '#101522')
    draw = ImageDraw.Draw(image)
    for x in range(1000):
        t = x / 999
        draw.line((x, 0, x, 9), fill=(int(70 + 160*t), int(200 - 65*t), int(220 - 110*t)))

    def font(size):
        try:
            return ImageFont.truetype('DejaVuSans.ttf', size)
        except OSError:
            try:
                return ImageFont.load_default(size=size)
            except TypeError:
                return ImageFont.load_default()

    def text(x, y, value, size=25, color='#ecf3ff', width=900):
        value = str(value)
        selected = font(size)
        while draw.textbbox((0, 0), value, font=selected)[2] > width and len(value) > 1:
            value = value[:-2] + '~'
        draw.text((x, y), value, fill=color, font=selected)

    text(44, 32, 'MP3z', 52)
    text(46, 101, 'DEINE MUSIK. DEIN SERVER.', 18, '#a7b6cc')
    draw.rounded_rectangle((736, 42, 956, 96), radius=25, fill='#233858' if daily else '#153d35')
    draw.ellipse((753, 61, 767, 75), fill='#93c5fd' if daily else '#6ee7b7')
    text(783, 55, 'TAGESSTATUS' if daily else 'HTTP BEREIT', 18, '#bfdbfe' if daily else '#a4f4d3', 160)
    text(44, 146, 'Tagesstatus 22:00' if daily else 'Dienst gestartet', 32)
    items = [('TITEL IM INDEX', values['count']), ('SPEICHER', values['storage']),
             ('INDEX', values['index']), ('LAUFZEIT', values['uptime'])]
    for i, (label, value) in enumerate(items):
        x, y = 44 + (i % 2)*466, 210 + (i // 2)*140
        draw.rounded_rectangle((x, y, x+442, y+120), radius=18, fill='#1b2638', outline='#304059', width=2)
        text(x+22, y+17, label, 16, '#a7b6cc', 398)
        color = '#fbbf60' if label == 'INDEX' and status.get('building') else '#edf5ff'
        text(x+22, y+48, value, 32, color, 398)
    text(44, 523, now.strftime('%d.%m.%Y  %H:%M %Z'), 19, '#a7b6cc')
    text(735, 523, 'HIGHFISH AI', 19, '#7dd3d6', 220)
    output = io.BytesIO()
    image.save(output, 'JPEG', quality=90, optimize=True)
    return output.getvalue()


def send_startup(bot, chat, status, uptime, now, daily=False):
    payload = {'chat_id': chat, 'caption': caption(status, uptime, now, daily=daily), 'parse_mode': 'HTML'}
    url = getattr(bot, 'url', None)
    if url:
        payload['reply_markup'] = {'inline_keyboard': [[{'text': '🎧 Webplayer öffnen', 'url': url}]]}
    try:
        image = render(status, uptime, now, daily=daily)
        bot.call('sendPhoto', payload, image=image)
    except Exception:
        payload['text'] = payload.pop('caption')
        bot.call('sendMessage', payload)
