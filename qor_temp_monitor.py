import tkinter as tk
from tkinter import ttk
import requests
import sqlite3
from email.mime.text import MIMEText
import smtplib
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime, date

# Configurações
target_url = "http://192.168.3.203"
check_interval = 1  # 1 segundo para exemplo
alert_temp = 60  # Temperatura limite para alerta
email_recipient = "contato.tecnica.epc@mailo.com"
email_sender = "contato.tecnica.epc@mailo.com"
email_password = "Tecnica@123"

# Função para converter data para string ao salvar no banco
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_converter("DATE", lambda s: datetime.strptime(s.decode(), "%Y-%m-%d").date())

# Criar conexão com conversor ativado
conn = sqlite3.connect(
    "temperaturas.db",
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
)

c = conn.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS temperatura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE,
        hora TIME,
        cpu_temp REAL,
        dsp_temp REAL,
        codecs_temp REAL
    )
""")
conn.commit()

def get_qor_status():
    try:
        response = requests.get(target_url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        def extract_temp(label):
            temp_element = soup.find(string=label)
            if temp_element:
                temp_value = temp_element.find_next().text.strip().replace("°C", "").replace("+", "")
                return float(temp_value)
            return None

        cpu_temp = extract_temp("CPU temp:")
        dsp_temp = extract_temp("DSP temp:")
        codecs_temp = extract_temp("Codecs temp:")

        return cpu_temp, dsp_temp, codecs_temp
    except Exception as e:
        print(f"Erro ao coletar status do QOR: {e}")
        return None, None, None

def save_temperature(cpu_temp, dsp_temp, codecs_temp):
    try:
        data_hoje = datetime.now().date()
        hora_atual = datetime.now().time().strftime("%H:%M:%S")  # Converte para string no formato HH:MM:SS

        # Inserindo as temperaturas no banco de dados
        c.execute("""
            INSERT INTO temperatura (data, hora, cpu_temp, dsp_temp, codecs_temp)
            VALUES (?, ?, ?, ?, ?)
        """, (data_hoje, hora_atual, cpu_temp, dsp_temp, codecs_temp))
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao salvar as temperaturas: {e}")


# Configurações iniciais
last_email_sent = None  # Variável para armazenar a hora do último envio de e-mail

def send_email(cpu_temp, dsp_temp, codecs_temp):
    global last_email_sent  # Usar a variável global para controlar o envio de e-mails

    # Definir o intervalo mínimo entre os e-mails (por exemplo, 12 horas)
    email_interval = 12 * 60 * 60  # 12 horas em segundos
    current_time = datetime.now()

    # Verificar se já passou o intervalo mínimo desde o último envio
    if last_email_sent is None or (current_time - last_email_sent).total_seconds() >= email_interval:
        try:
            msg_content = f"""
            ALERTA: Uma das temperaturas do QOR ultrapassou {alert_temp}°C.
            Temperaturas registradas:
            - CPU: {cpu_temp}°C
            - DSP: {dsp_temp}°C
            - Codecs: {codecs_temp}°C
            Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            msg = MIMEText(msg_content)
            msg["Subject"] = "ALERTA DE TEMPERATURA - QOR"
            msg["From"] = email_sender
            msg["To"] = email_recipient

            with smtplib.SMTP("mail.mailo.com", 587) as server:
                server.starttls()
                server.login(email_sender, email_password)
                server.sendmail(email_sender, email_recipient, msg.as_string())

            print("Email de alerta enviado!")
            last_email_sent = current_time  # Atualizar a hora do último envio
        except Exception as e:
            print(f"Erro ao enviar email: {e}")
    else:
        print("O e-mail já foi enviado recentemente, aguardando próximo intervalo.")

# Interface gráfica com tkinter
class TempMonitorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Monitor de Temperaturas - QOR")
        self.geometry("600x400")
        
        self.current_label = ttk.Label(self, text="Temperaturas Atuais:", font=("Arial", 14))
        self.current_label.pack(pady=10)
        
        self.cpu_label = ttk.Label(self, text="CPU Temp: -- °C", font=("Arial", 12))
        self.cpu_label.pack()
        
        self.dsp_label = ttk.Label(self, text="DSP Temp: -- °C", font=("Arial", 12))
        self.dsp_label.pack()
        
        self.codecs_label = ttk.Label(self, text="Codecs Temp: -- °C", font=("Arial", 12))
        self.codecs_label.pack()
        
        self.db_label = ttk.Label(self, text="Temperaturas no Banco de Dados:", font=("Arial", 14))
        self.db_label.pack(pady=10)
        
        self.db_text = tk.Text(self, height=10, width=70)
        self.db_text.pack()
        
        self.update_temperature_data()

    def update_temperature_data(self):
        cpu_temp, dsp_temp, codecs_temp = get_qor_status()

        if cpu_temp is not None and dsp_temp is not None and codecs_temp is not None:
            self.cpu_label.config(text=f"CPU Temp: {cpu_temp} °C")
            self.dsp_label.config(text=f"DSP Temp: {dsp_temp} °C")
            self.codecs_label.config(text=f"Codecs Temp: {codecs_temp} °C")
            
            save_temperature(cpu_temp, dsp_temp, codecs_temp)

            if cpu_temp > alert_temp or dsp_temp > alert_temp or codecs_temp > alert_temp:
                send_email(cpu_temp, dsp_temp, codecs_temp)

        # # Consultar e exibir as últimas temperaturas salvas no banco de dados
        # self.db_text.delete(1.0, tk.END)  # Limpa o texto atual
        # c.execute("SELECT * FROM temperatura ORDER BY data DESC LIMIT 5")
        # rows = c.fetchall()
        # for row in rows:
        #     self.db_text.insert(tk.END, f"Data: {row[1]}, CPU: {row[2]}°C / {row[3]}°C / {row[4]}°C, DSP: {row[5]}°C / {row[6]}°C / {row[7]}°C, Codecs: {row[8]}°C / {row[9]}°C / {row[10]}°C\n")
        
        # Atualizar a cada check_interval segundos
        self.after(check_interval * 1000, self.update_temperature_data)

if __name__ == "__main__":
    app = TempMonitorApp()
    app.mainloop()
