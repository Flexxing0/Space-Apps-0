"""Envío de avisos por correo electrónico vía SMTP con variables de entorno.

Nunca almacena credenciales en código ni envía correos sin consentimiento
explícito del usuario y configuración SMTP activa en el entorno.
"""
from email.message import EmailMessage
import html
import os
import re
import smtplib
import ssl


EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and bool(EMAIL_RE.fullmatch(value.strip()))


def smtp_config():
    host = os.environ.get('EARTHLENS_SMTP_HOST', '').strip()
    user = os.environ.get('EARTHLENS_SMTP_USER', '').strip()
    password = os.environ.get('EARTHLENS_SMTP_PASS', '').replace(' ', '').strip()
    port_raw = os.environ.get('EARTHLENS_SMTP_PORT', '587').strip()
    sender = os.environ.get('EARTHLENS_SMTP_FROM', '').strip() or user
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'sender': sender,
    }


def is_configured():
    cfg = smtp_config()
    return bool(cfg['host'] and cfg['user'] and cfg['password'] and cfg['sender'])


def send_email(to_email, subject, text_body, html_body=None):
    if not valid_email(to_email):
        raise ValueError('Dirección de correo inválida.')
    cfg = smtp_config()
    if not (cfg['host'] and cfg['user'] and cfg['password'] and cfg['sender']):
        raise RuntimeError('SMTP no configurado en el servidor.')

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"EarthLens Avisos <{cfg['sender']}>"
    msg['To'] = to_email.strip()
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype='html')

    context = ssl.create_default_context()
    if cfg['port'] == 465:
        with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=20, context=context) as server:
            server.login(cfg['user'], cfg['password'])
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(cfg['user'], cfg['password'])
            server.send_message(msg)


def send_test_email(to_email, username):
    subject = 'EarthLens · Correo de avisos conectado correctamente'
    text = (
        f"Hola {username},\n\n"
        "Tu correo quedó conectado a los avisos climáticos de EarthLens Argentina.\n"
        "Cuando guardes un evento con seguimiento activo y cambie el pronóstico, te avisaremos por acá.\n\n"
        "— EarthLens"
    )
    body_html = f"""
    <div style="font-family:Inter,Segoe UI,Arial,sans-serif;background:#0b1623;color:#f1f5f9;padding:24px;border-radius:12px;max-width:540px;margin:auto">
      <div style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#38d9a9;margin-right:8px"></div>
      <strong style="font-size:18px;color:#ffffff">EarthLens</strong>
      <span style="font-size:11px;color:#8ca2b8;letter-spacing:1.5px;margin-left:6px">ARGENTINA</span>
      <h2 style="color:#38d9a9;margin:18px 0 8px;font-size:18px">¡Avisos por correo activos!</h2>
      <p style="color:#cbd5e1;font-size:14px;line-height:1.5">
        Hola <strong>@{html.escape(username)}</strong>, confirmamos que tu correo quedó vinculado correctamente a tu cuenta.
      </p>
      <p style="color:#cbd5e1;font-size:14px;line-height:1.5">
        Cada vez que crees un evento con seguimiento o cambie el pronóstico de temperatura, lluvia o viento para tus actividades, recibirás un aviso automático aquí.
      </p>
    </div>
    """
    send_email(to_email, subject, text, body_html)


def send_event_alert(to_email, event, title, message, *, changes=None, recommendation='', city_name=''):
    changes = changes or []
    event_name = event.get('name', 'Tu evento')
    date_str = str(event.get('start', ''))[:10]
    time_str = str(event.get('start', ''))[11:16]
    place = event.get('location_label') or city_name or event.get('city_id', '')
    subject = f"EarthLens · {title}: {event_name}"

    changes_lines = [
        f"- {c.get('criterion', '')}: {c.get('previous_value')} -> {c.get('current_value')} {c.get('unit', '')}"
        for c in changes
    ]
    text_parts = [
        f"Aviso climático de EarthLens para tu evento: {event_name}",
        f"Fecha y hora: {date_str} a las {time_str} hs",
        f"Lugar: {place}",
        "",
        message,
    ]
    if changes_lines:
        text_parts.extend(["", "Cambios detectados:", *changes_lines])
    if recommendation:
        text_parts.extend(["", f"Recomendación: {recommendation}"])
    text_parts.extend(["", "Podés revisar la predicción actualizada abriendo EarthLens."])

    changes_html = ''
    if changes:
        rows = ''.join(
            f"<li style='margin:4px 0;color:#e2e8f0'><strong>{html.escape(str(c.get('criterion','')))}:</strong> "
            f"{html.escape(str(c.get('previous_value')))} &rarr; <strong>{html.escape(str(c.get('current_value')))} {html.escape(str(c.get('unit','')))}</strong></li>"
            for c in changes
        )
        changes_html = f"<ul style='padding-left:18px;margin:10px 0'>{rows}</ul>"

    rec_html = (
        f"<div style='background:rgba(56,217,169,0.12);border:1px solid rgba(56,217,169,0.35);border-radius:10px;padding:12px;margin-top:12px;color:#e2e8f0;font-size:13.5px'>"
        f"<strong>Recomendación:</strong> {html.escape(recommendation)}</div>"
    ) if recommendation else ''

    html_body = f"""
    <div style="font-family:Inter,Segoe UI,Arial,sans-serif;background:#0b1623;color:#f1f5f9;padding:24px;border-radius:14px;max-width:560px;margin:auto">
      <div style="margin-bottom:14px">
        <span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#38d9a9;margin-right:6px"></span>
        <strong style="font-size:17px;color:#ffffff">EarthLens</strong>
        <span style="font-size:11px;color:#8ca2b8;letter-spacing:1.4px;margin-left:5px">ARGENTINA</span>
      </div>
      <div style="background:#142438;border:1px solid rgba(148,184,218,0.18);border-radius:12px;padding:16px">
        <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#38d9a9;text-transform:uppercase;letter-spacing:0.8px">{html.escape(title)}</p>
        <h2 style="margin:0 0 6px;font-size:19px;color:#ffffff">{html.escape(event_name)}</h2>
        <p style="margin:0 0 12px;font-size:13px;color:#94a3b8">{html.escape(date_str)} · {html.escape(time_str)} hs · {html.escape(place)}</p>
        <p style="margin:0;font-size:14px;color:#e2e8f0;line-height:1.5">{html.escape(message)}</p>
        {changes_html}
        {rec_html}
      </div>
    </div>
    """
    send_email(to_email, subject, '\n'.join(text_parts), html_body)
