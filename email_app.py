from flask import Flask, render_template_string, request
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email import encoders
import mimetypes
import os
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_FORM = '''
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Envio de E-mails</title>
  <style>
    body {
      background-color: #000;
      color: #fff;
      font-family: Arial, sans-serif;
      padding: 20px;
    }
    textarea, input[type="text"], input[type="email"], input[type="password"], input[type="number"] {
      width: 100%;
      padding: 8px;
      margin-bottom: 15px;
      border: none;
      border-radius: 4px;
    }
    button {
      background-color: #28a745;
      color: white;
      padding: 12px 24px;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      font-size: 16px;
    }
    button:hover {
      background-color: #218838;
    }
    .counter {
      font-size: 14px;
      color: #aaa;
      margin-bottom: 10px;
    }
  </style>
  <script>
    function contarDestinatarios() {
      const texto = document.getElementById("destinatarios").value;
      const linhas = texto.split(/\r?\n/).filter(l => l.trim() !== "");
      document.getElementById("contador").innerText = "Destinat\u00e1rios adicionados: " + linhas.length;
    }
  </script>
</head>
<body>
  <h2>Configura\u00e7\u00e3o de E-mails</h2>
  <form method="POST" enctype="multipart/form-data">
    <p>Email Remetente: <input type="email" name="email" value="{{ email or '' }}" required></p>
    <p>Senha do Email: <input type="password" name="senha" required></p>
    <p>Destinat\u00e1rios (um por linha):<br>
      <textarea id="destinatarios" name="destinatarios" rows="10" cols="50" oninput="contarDestinatarios()" required>{{ destinatarios or '' }}</textarea>
    </p>
    <p class="counter" id="contador">Destinat\u00e1rios adicionados: {{ contador or 0 }}</p>
    <p>Assunto: <input type="text" name="assunto" value="{{ assunto or '' }}" required></p>
    <p>Mensagem (HTML permitido):<br>
      <textarea name="mensagem" rows="10" cols="50" required>{{ mensagem or '' }}</textarea></p>
    <p>Assinatura (HTML permitido):<br>
      <textarea name="assinatura" rows="5" cols="50" required>{{ assinatura or '' }}</textarea></p>
    <p>Tempo entre envios (segundos): <input type="number" name="tempo_envio" value="{{ tempo_envio or 60 }}" min="1" required></p>
    <p>Arquivos para anexar: <input type="file" name="anexos" multiple></p>
    <p><button type="submit">\ud83d\ude80 Enviar Emails</button></p>
  </form>
</body></html>
'''

HTML_RESULTADO = '''
<!doctype html>
<html lang="pt-br">
<head><meta charset="utf-8"><title>Relat\u00f3rio</title></head>
<body style="background-color:#000;color:#fff;font-family:Arial;padding:20px;">
  <h2>Relat\u00f3rio de Envio</h2>
  <ul>{% for log in logs %}<li>{{ log }}</li>{% endfor %}</ul>
  <p>Total de e-mails enviados: {{ contador_emails }}</p>
  <p><a href="/" style="color:#0af;">Voltar</a></p>
</body></html>
'''

# Armazena dados do \u00faltimo envio para manter preenchido
ultimo_envio = {}


def extrair_primeiro_nome(email):
    return email.split('@')[0].split('.')[0].capitalize()


def anexar_arquivo(msg, caminho):
    mime_type, _ = mimetypes.guess_type(caminho)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    main_type, sub_type = mime_type.split('/', 1)
    with open(caminho, 'rb') as f:
        if main_type == 'text':
            part = MIMEText(f.read().decode('utf-8'), _subtype=sub_type)
        elif main_type == 'image':
            part = MIMEImage(f.read(), _subtype=sub_type)
        elif main_type == 'application':
            part = MIMEApplication(f.read(), _subtype=sub_type)
        else:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
            encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(caminho))
    msg.attach(part)


def send_email(email, senha, destinatario, assunto, mensagem, assinatura_html, anexos_paths):
    primeiro_nome = extrair_primeiro_nome(destinatario)
    corpo = f"Ol\u00e1, {primeiro_nome},<br><br>{mensagem}<br><br>{assinatura_html}"
    msg = MIMEMultipart()
    msg['From'] = email
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)
    msg_html = MIMEText(corpo, 'html')
    msg_alternative.attach(msg_html)
    for caminho in anexos_paths:
        anexar_arquivo(msg, caminho)
    server = smtplib.SMTP('smtp.agpr5.com', 587)
    server.starttls()
    server.login(email, senha)
    server.send_message(msg)
    server.quit()


@app.route('/', methods=['GET', 'POST'])
def index():
    global ultimo_envio
    if request.method == 'POST':
        email_remetente = request.form['email']
        senha_email = request.form['senha']
        destinatarios_texto = request.form['destinatarios']
        destinatarios = [d.strip() for d in destinatarios_texto.splitlines() if d.strip()]
        assunto = request.form['assunto']
        mensagem = request.form['mensagem']
        assinatura = request.form['assinatura']
        tempo_envio = int(request.form['tempo_envio'])
        anexos_paths = []
        for arquivo in request.files.getlist('anexos'):
            if arquivo and arquivo.filename:
                caminho = os.path.join(UPLOAD_FOLDER, arquivo.filename)
                arquivo.save(caminho)
                anexos_paths.append(caminho)
        logs = []
        contador_emails = 0
        for destinatario in destinatarios:
            try:
                send_email(email_remetente, senha_email, destinatario, assunto, mensagem, assinatura, anexos_paths)
                logs.append(f"\u2705 Email enviado para {destinatario}")
                contador_emails += 1
            except Exception as e:
                logs.append(f"\u274c Erro ao enviar para {destinatario}: {e}")
            time.sleep(tempo_envio)
        ultimo_envio = {
            'email': email_remetente,
            'destinatarios': destinatarios_texto,
            'assunto': assunto,
            'mensagem': mensagem,
            'assinatura': assinatura,
            'tempo_envio': tempo_envio
        }
        return render_template_string(HTML_RESULTADO, logs=logs, contador_emails=contador_emails)
    # GET
    return render_template_string(
        HTML_FORM,
        email=ultimo_envio.get('email',''),
        destinatarios=ultimo_envio.get('destinatarios',''),
        assunto=ultimo_envio.get('assunto',''),
        mensagem=ultimo_envio.get('mensagem',''),
        assinatura=ultimo_envio.get('assinatura',''),
        tempo_envio=ultimo_envio.get('tempo_envio',60),
        contador=len(ultimo_envio.get('destinatarios','').splitlines()) if ultimo_envio else 0
    )


if __name__ == '__main__':
    app.run(debug=True)
