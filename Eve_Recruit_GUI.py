import tkinter
from tkinter import *
from tkinter import messagebox as mb
from tkinter import simpledialog as sdialog
import sqlite3
import pyperclip
import time
import json
import threading
import requests
import base64
import urllib.parse
import datetime
import os
import webbrowser

from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# pip install python-jose[cryptography]
from jose import jwt

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))

# Работа с базой данных
class MainDatabase:
    def __init__(self):
        self.filename = 'users.db'
        self.session = sqlite3.connect(os.path.join(ROOT_PATH, "users.db"))
        self.db_init()

    def db_init(self):
        sql_create_table_users = 'CREATE TABLE IF NOT EXISTS users (' \
                                 'id INTEGER PRIMARY KEY,' \
                                 'sent INTEGER,' \
                                 'char_name VARCHAR)'

        self.session.execute(sql_create_table_users)
        self.session.commit()

        sql_create_table_config = 'CREATE TABLE IF NOT EXISTS config (' \
                                  'param VARCHAR PRIMARY KEY,' \
                                  'data VARCHAR)'

        self.session.execute(sql_create_table_config)
        self.session.commit()

        sql_create_table_mail = 'CREATE TABLE IF NOT EXISTS mail (' \
                                'id INTEGER PRIMARY KEY,' \
                                'subject VARCHAR,' \
                                'body VARCHAR)'

        self.session.execute(sql_create_table_mail)
        self.session.commit()
        
        sql_create_first_mail = 'INSERT OR IGNORE INTO mail(id,subject,body)'\
                                'VALUES (0,\'This is first message\', \'Hello! i`m test message\')'
                                
        self.session.execute(sql_create_first_mail)
        self.session.commit()
        
    def bulk_check(self, all_users):
        users_to_add = []
        # В одном выражении не может быть больше 500 select/union, поэтому обрабатываем порциями.
        for i in range(0, len(all_users), 500):
            SQL_select = 'CREATE TEMPORARY TABLE TEMP_TABLE2 AS Select "' + '" as nick union select "'.join(
                all_users[i:i + 500]) + '" as nick'
            self.session.execute(SQL_select)
            SQL_select = 'select T1.nick from TEMP_TABLE2 as T1 left join users as users on users.char_name = T1.nick where users.char_name is null'
            rez = self.session.execute(SQL_select)
            rows_to_add = rez.fetchall()
            for row in rows_to_add:
                users_to_add.append(row[0])
            SQL_select = 'drop table TEMP_TABLE2'
            self.session.execute(SQL_select)

        return users_to_add

    def bulk_add(self, users_to_add):
        SQL_select = 'INSERT INTO users (char_name, sent) VALUES("' + '", 0),("'.join(users_to_add) + '", 0)'
        rez = self.session.execute(SQL_select)
        self.session.commit()

    def add_mail(self, subject, body):
        SQL_select = 'INSERT or REPLACE INTO mail (id, subject, body) VALUES(1, ?, ?)'
        rez = self.session.execute(SQL_select, (subject, body))
        self.session.commit()

    def get_mail_variants(self):
        list_of_mail_variants = []
        SQL_select = 'Select id, subject, body from mail'
        rez = self.session.execute(SQL_select)
        rows_to_add = rez.fetchall()
        keys = ('id', 'subject', 'body')
        for row in rows_to_add:
            list_of_mail_variants.append(dict(zip(keys, row)))
        return list_of_mail_variants

    def delete_mail_variant(self, id):
        SQL_select = f'delete from mail where ID = {id}'
        rez = self.session.execute(SQL_select)
        return rez

    def get_mail_variant(self, id):
        SQL_select = f'Select subject, body from mail where id = {id}'
        rez = self.session.execute(SQL_select).fetchone()
        if not rez:
            return '', ''
        else:
            return rez[0], rez[1]

    def get_base_stats(self):
        SQL_select = ('Select '
                      'count(1) as total, '
                      'sum(case when sent = 1 then 1 else 0 end) as sent, '
                      'sum(case when sent = 0 then 1 else 0 end) as not_sent, '
                      'sum(case when sent = 9 then 1 else 0 end) as unfind '
                      'from users')

        rez = self.session.execute(SQL_select)
        result = rez.fetchone()
        keys = ('total', 'sent', 'not_sent', 'unfind')
        return dict(zip(keys, result))

    def get_unfind_nicks_to_send(self):
        nicks_to_send = []
        SQL_select = 'Select char_name from users where sent = 9 limit 50'
        rez = self.session.execute(SQL_select)
        rows_to_add = rez.fetchall()
        for row in rows_to_add:
            nicks_to_send.append(row[0])
        return nicks_to_send

    def get_nicks_to_send(self):
        nicks_to_send = []
        SQL_select = 'Select char_name from users where sent = 0 limit 50'
        rez = self.session.execute(SQL_select)
        rows_to_add = rez.fetchall()
        for row in rows_to_add:
            nicks_to_send.append(row[0])
        return nicks_to_send

    def mark_as_sent(self, nicks):
        SQL_select = 'update users set sent = 1 where char_name in ("' + '", "'.join(nicks) + '")'
        rez = self.session.execute(SQL_select)
        self.session.commit()

    def mark_as_unfinded(self, nicks):
        SQL_select = 'update users set sent = 9 where char_name in ("' + '", "'.join(nicks) + '")'
        rez = self.session.execute(SQL_select)
        self.session.commit()

    def mark_as_blockmessage(self, nicks):
        SQL_select = 'update users set sent = 8 where char_name in ("' + '", "'.join(nicks) + '")'
        rez = self.session.execute(SQL_select)
        self.session.commit()

    def get_config(self):
        config = {}
        SQL_select = 'Select param, data from config'
        rez = self.session.execute(SQL_select)
        while True:
            next_row = rez.fetchone()
            if next_row:
                param = next_row[0]
                if param in ('expires_in', 'selected_mail_variant'):
                    data = int(next_row[1])
                elif param == 'time':
                    data = float(next_row[1])
                else:
                    data = next_row[1]
                config[param] = data

            else:
                break
        return config

    def put_config(self):
        values = []
        for key, value in config.items():
            values.append(f'"{key}","{value}"')
        SQL_select = 'INSERT OR REPLACE INTO config (param, data) VALUES(' + '),('.join(values) + ')'
        rez = self.session.execute(SQL_select)
        self.session.commit()


def print_stats(db):
    db_stats = db.get_base_stats()
    message = f'''
    Всего никнеймов в базе: {db_stats.get('total')}
    Отправлено: {db_stats.get('sent')}
    Не отправлено: {db_stats.get('not_sent')}
    Не найденных через API: {db_stats.get('unfind')}
    Текущий выбранный вариант письма для отправки через API: {config["selected_mail_variant"]}
    '''
    text_box.delete('1.0', END)
    text_box.insert(END, message)


# Мини web-сервер для первичного получения кода авторизации
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    # определяем метод `do_GET`
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

        # разбираем GET запрос по параметрам
        get_params = parse_qs(urlparse(self.path).query)
        self.wfile.write(b'Registration complete')

        # получаем код авторизации

        global auth_code
        if get_params.get('code', False) != False:
            auth_code = get_params['code'][0]


class MyServer(threading.Thread):
    def run(self):
        self.server = ThreadingHTTPServer(('localhost', 8000), SimpleHTTPRequestHandler)
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()


# Аутентефикация, получение и обновление токена
def validate_eve_jwt(jwt_token):
    jwk_set_url = "https://login.eveonline.com/oauth/jwks"
    res = requests.get(jwk_set_url)
    res.raise_for_status()
    data = res.json()
    jwk_sets = data["keys"]
    jwk_set = next((item for item in jwk_sets if item["alg"] == "RS256"))
    return jwt.decode(jwt_token,
                      jwk_set,
                      algorithms=jwk_set["alg"],
                      issuer="login.eveonline.com",
                      audience='EVE Online')


def refresh_token():
    global config
    # формирование массива данных для авторизации
    auth_payload = {'grant_type': 'refresh_token',
                    'refresh_token': config['refresh_token']}

    # формирование заголовка HTTP для запроса авторизации
    header_post = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Accept': 'application/json',
                   'Host': params["login_server_base_url"],
                   'Authorization': f'Basic {params["authorization_code"]}'}

    eve_online_url = f'https://{params["login_server_base_url"]}/v2/oauth/token'

    # запрашиваем данные для авторизации у CCP
    auth_data = requests.post(url=eve_online_url, headers=header_post, data=auth_payload).json()

    config = {'access_token': auth_data['access_token'],
              'token_type': auth_data['token_type'],
              'expires_in': auth_data['expires_in'],
              'refresh_token': auth_data['refresh_token'],
              'time': time.time(),
              'client_id': config['client_id'],
              'secret_key': config['secret_key'],
              'selected_mail_variant': config['selected_mail_variant']}

    put_config()


def full_auth():
    t_client_id = sdialog.askstring(title="Авторизация", prompt="Конфиг в базе не заполнен, проводим полную авторизацию.\nВведите ваш Client_ID: ")
    t_secret_key = sdialog.askstring(title="Авторизация", prompt="Конфиг в базе не заполнен, проводим полную авторизацию.\nВведите ваш secret_key: ")
    params["authorization_code"] = base64.b64encode(f'{t_client_id}:{t_secret_key}'.encode('UTF-8')).decode('UTF-8')

    url = f'https://{params["login_server_base_url"]}/v2/oauth/authorize?response_type={params["response_type"]}&redirect_uri={params["callback_url"]}&' \
          f'client_id={t_client_id}&scope={params["scopes"]}&state={params["state"]}'

    global auth_code
    web_server = MyServer()
    web_server.start()
    print('server alive:', web_server.is_alive())  # True
    print('------------------')
    print('Your registration URL')
    print(url)
    print('------------------')
    webbrowser.open(url)
    while auth_code == '':
        pass
    web_server.stop()
    print('server alive:', web_server.is_alive())  # False

    # формирование массива данных для авторизации
    auth_payload = {'grant_type': 'authorization_code',
                    'code': f'{auth_code}'}

    # формирование заголовка HTTP для запроса авторизации
    header_post = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Accept': 'application/json',
                   'Host': params["login_server_base_url"],
                   'Authorization': f'Basic {params["authorization_code"]}'}
    eve_online_url = f'https://{params["login_server_base_url"]}/v2/oauth/token'

    # запрашиваем данные для авторизации у CCP
    auth_data = requests.post(url=eve_online_url, headers=header_post, data=auth_payload).json()

    global config
    config = {'access_token': auth_data['access_token'],
              'token_type': auth_data['token_type'],
              'expires_in': auth_data['expires_in'],
              'refresh_token': auth_data['refresh_token'],
              'client_id': t_client_id,
              'secret_key': t_secret_key,
              'time': time.time()}

    return config


def validate_and_get_id():
    # производим валидацию данных + узнаем id персонажа который авторизовался
    jwt = validate_eve_jwt(config['access_token'])
    params['character_id'] = jwt["sub"].split(":")[2]


# Сохранение и загрузка настроек
def get_config():
    config = db.get_config()
    if (config.get('access_token', False) == False
            or config.get('token_type', False) == False
            or config.get('expires_in', False) == False
            or config.get('refresh_token', False) == False
            or config.get('time', False) == False
            or config.get('client_id', False) == False
            or config.get('secret_key', False) == False):
        print(f'Конфиг в базе не заполнен, проводим полную авторизацию. Содержимое конфига: {config}')
        config = full_auth()
        put_config()

    if config.get('selected_mail_variant', False) == False:
        config['selected_mail_variant'] = 1
        put_config()

    params["authorization_code"] = base64.b64encode(
        f'{config["client_id"]}:{config["secret_key"]}'.encode('UTF-8')).decode('UTF-8')
    return config


def put_config():
    db.put_config()


# Запросы к API
def get_character_wallet(character_id):
    check_token()
    # получаем валлет данного персонажа
    header = {'Content-Type': 'application/x-www-form-urlencoded',
              'Accept': 'application/json',
              'Authorization': f'Bearer {config["access_token"]}'}

    route = f'/characters/{character_id}/wallet/'
    url_get = f'{params["eve_esi_url"]}{route}'
    wallet = requests.get(url_get, headers=header).json()
    return wallet


def send_mail(characters_id_to_send):
    check_token()

    if len(characters_id_to_send) == 0: return

    subject, body = db.get_mail_variant(config['selected_mail_variant'])

    header = {'Content-Type': 'application/json',
              'Accept': 'application/json',
              'Authorization': f'Bearer {config["access_token"]}',
              'Cache-Control': 'no-cache'}

    route = f'/characters/{params["character_id"]}/mail/'

    params_str = f'?datasource=tranquility'

    recipients = []

    for character_id in characters_id_to_send:
        recipients.append({"recipient_id": character_id, "recipient_type": "character"})

    mail = {"approved_cost": 10000000,
            "body": body,
            "recipients": recipients,
            "subject": subject}

    myjson = json.dumps(mail)

    url_post = f'{params["eve_esi_url"]}{route}{params_str}'
    result = requests.post(url_post, headers=header, json=mail)
    if result.status_code == 201:
        return True
    else:
        add_log(f'Отправка письма неуспешна. Результат отправки {result, result.json()}')
        error = result.json()['error'].split(', ')
        if error[0] == 'ContactOwnerUnreachable':
            nick_name = error[1].split(': ')[2].rstrip('"}').lstrip('"')
            db.mark_as_blockmessage([nick_name])
            add_log(f'Данный человек {nick_name} помечен как блокирующий рассылки, повторная попытка отправки писем.')
            characters_id_to_send.clear()
            return send_mail_api()

        return False

    return result


def get_character_id_mt(nickname):
    global characters_id_to_send, unfinded_characters

    safe_nickname = urllib.parse.quote_plus(nickname)
    # Получаем character ID по имени персонажа
    header = {'Content-Type': 'application/x-www-form-urlencoded',
              'Accept': 'application/json',
              'Authorization': f'Bearer {config["access_token"]}'}

    route = f'/characters/{params["character_id"]}/search/'
    params_str = f'?categories=character&datasource=tranquility&language=en&search={safe_nickname}&strict=true'
    url_get = f'{params["eve_esi_url"]}{route}{params_str}'
    CharacterID = requests.get(url_get, headers=header).json()
    if len(CharacterID) == 0:
        print(f'Для персонажа {nickname} не найден CharacterID, письмо отправлено не будет')
        unfinded_characters.append(nickname)
    else:
        characters_id_to_send.append(CharacterID['character'][0])


# Общие процедуры
def check_token():
    if time.time() - config["time"] + 10 > config["expires_in"]:
        refresh_token()


def get_characters_id(nicks_to_send):
    check_token()
    global characters_id_to_send, unfinded_characters
    unfinded_characters.clear()

    threads = []
    for nick in nicks_to_send:
        t = threading.Thread(target=get_character_id_mt, args=(nick,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    for nick in unfinded_characters:
        nicks_to_send.remove(nick)

    return characters_id_to_send, unfinded_characters


# Обработчики выбора пунктов меню
def add_new_nicknames():
    all_users = window.clipboard_get().splitlines()
    users_to_add = db.bulk_check(all_users)
    if len(users_to_add) == 0:
        add_log('Новых никнеймов не обнаружено')
    else:
        db.bulk_add(users_to_add)
        add_log(f'Новых никнеймов добавлено: {len(users_to_add)}')
    print_stats(db)


def gen_unfind_nickname_pack():
    nicks_to_send = db.get_unfind_nicks_to_send()
    add_log(f'Ненайденные через API никнеймы к ручной отправке: {", ".join(nicks_to_send)}')
    pyperclip.copy(', '.join(nicks_to_send))

    res = mb.askquestion('Yes/No', 'Письма отправлены и можно отмечать факт отправки в базе? [yes/no]')

    if res == 'yes':
        db.mark_as_sent(nicks_to_send)
    else:
        add_log('Внимание! Вышеперечисленные никнеймы не были отмеченв в базе данных и снова появятся в списке при следующей обработке!')
    print_stats(db)


def gen_nickname_pack():
    nicks_to_send = db.get_nicks_to_send()
    add_log(f'Никнеймы к отправке: {", ".join(nicks_to_send)}')
    pyperclip.copy(', '.join(nicks_to_send))

    res = mb.askquestion('Yes/No', 'Письма отправлены и можно отмечать факт отправки в базе? [yes/no]')

    if res == 'yes':
        db.mark_as_sent(nicks_to_send)
    else:
        add_log(
            'Внимание! Вышеперечисленные никнеймы не были отмеченв в базе данных и снова появятся в списке при следующей обработке!')
    print_stats(db)


def send_mail_api():
    nicks_to_send = db.get_nicks_to_send()
    add_log('Подготовка к отправке')
    characters_id_to_send, unfinded_characters = get_characters_id(nicks_to_send)
    result = send_mail(characters_id_to_send)
    if result:
        db.mark_as_sent(nicks_to_send)
        db.mark_as_unfinded(unfinded_characters)
        add_log('Отправка прошла успешно')
    characters_id_to_send.clear()
    unfinded_characters.clear()
    print_stats(db)


def send_mail_api_one_nickname(one_nickname_entry, add_main_param):
    nicks_to_send = [one_nickname_entry.get()]
    characters_id_to_send, unfinded_characters = get_characters_id(nicks_to_send)
    result = send_mail(characters_id_to_send)
    if result: db.mark_as_sent(nicks_to_send)
    print_stats(db)
    add_log(f'Письмо: {nicks_to_send[0]} - отправлено')
    return add_main_param.destroy()


def add_mail_one_nickname_window():
    add_main_param = Toplevel(window)
    add_main_param.grab_set()
    lbl = Label(add_main_param, text='Ведите nickname:', anchor='w', justify=LEFT)
    lbl.grid(column=0, row=0, padx=10, pady=5)
    one_nickname = StringVar()
    one_nickname_entry = Entry(add_main_param, textvariable=one_nickname)
    one_nickname_entry.grid(column=1, row=0, padx=10)
    add_subject_btn = Button(add_main_param, text='Send', width=10,
                             command=lambda: send_mail_api_one_nickname(one_nickname_entry, add_main_param))
    add_subject_btn.grid(column=0, row=1, padx=10, pady=5)
    cancel_subject_btn = Button(add_main_param, text='Cancel', width=10,
                                command=lambda: add_main_param.destroy())
    cancel_subject_btn.grid(column=1, row=1, padx=10, pady=5)


def add_mail_main_window():
    subject, body = db.get_mail_variant(config['selected_mail_variant'])
    change_mail = Toplevel(window)
    change_mail.grab_set()
    lbl = Label(change_mail, text='Subject:', anchor='w', justify=LEFT)
    lbl.grid(column=0, row=0, padx=10, pady=5)
    mail_subject = StringVar(value=subject)
    mail_subject_entry = Entry(change_mail, textvariable=mail_subject, width=76)
    mail_subject_entry.grid(column=1, row=0, padx=10, columnspan=2)
    mail_body_text = Text(change_mail, width=80)
    mail_body_text.grid(column=0, row=1, padx=10, columnspan=3, ipady=60)
    mail_body_text.insert('end', body)
    add_subject_btn = Button(change_mail, text='OK', width=10,
                             command=lambda: add_mail(mail_subject_entry, change_mail, mail_body_text))
    add_subject_btn.grid(column=0, row=4, padx=10, pady=5, columnspan=2)
    cancel_subject_btn = Button(change_mail, text='Cancel', width=10,
                                command=lambda: change_mail.destroy())
    cancel_subject_btn.grid(column=2, row=4, padx=10, pady=5)


def add_mail(mail_subject_entry, change_mail, mail_body_text):
    mail_subject = mail_subject_entry.get()
    mail_body = mail_body_text.get(0.0, 'end').strip()
    check_mail_url = mail_body.replace('\n', ' \n').split(' ')
    for one_word in range(len(check_mail_url)):
        if check_mail_url[one_word].startswith(('http://', 'https://')):
            check_mail_url[one_word] = '<a href="' + check_mail_url[one_word] + f'">{check_mail_url[one_word]}</a>'
        elif check_mail_url[one_word].startswith(('\nhttp://', '\nhttps://')):
            check_mail_url[one_word] = '\n<a href="' + check_mail_url[one_word].lstrip() + f'">{check_mail_url[one_word].lstrip()}</a>'
        elif check_mail_url[one_word].startswith('www.'):
            check_mail_url[one_word] = '<a href="http://' + check_mail_url[one_word] + f'">{check_mail_url[one_word]}</a>'
        elif check_mail_url[one_word].startswith('\nwww.'):
            check_mail_url[one_word] = '\n<a href="http://' + check_mail_url[one_word].lstrip() + f'">{check_mail_url[one_word].lstrip()}</a>'
    mail_body = ' '.join(check_mail_url)
    add_log(f'Письмо с темой: "{mail_subject}" - добавлено')
    add_log('Текст добавленного письма:')
    add_log(f'{mail_body}')
    db.add_mail(mail_subject, mail_body)
    return change_mail.destroy()


def select_mail():
    list_of_mail_variants = db.get_mail_variants()
    print('На данный момент в базе сохранены следующие варианты писем:')
    print(*list_of_mail_variants, sep='\n')
    print('--------------------------------------------')
    print(f'Текущий выбранный вариант письма: {config["selected_mail_variant"]}')
    config['selected_mail_variant'] = input('Выберите вариант письма для последующих отправок: ')
    put_config()


def delete_mail():
    mail_variant_to_delete = input('Укажите номер варианта письма, который нужно удалить: ')
    db.delete_mail_variant(mail_variant_to_delete)


def get_last_mail():
    check_token()
    # Получим ID последнего письма
    header = {'Accept': 'application/json',
              'Authorization': f'Bearer {config["access_token"]}'}
    # 'Content-Type': 'application/x-www-form-urlencoded',

    route = f'/characters/{params["character_id"]}/mail/'
    params_str = f'?datasource=tranquility'
    url_get = f'{params["eve_esi_url"]}{route}{params_str}'
    mails = requests.get(url_get, headers=header).json()
    mail_id = mails[0]['mail_id']

    # Получим текст и тему письма по id
    header = {'Accept': 'application/json',
              'Authorization': f'Bearer {config["access_token"]}'}
    # 'Content-Type': 'application/x-www-form-urlencoded',

    route = f'/characters/{params["character_id"]}/mail/{mail_id}/'
    params_str = f'?datasource=tranquility'
    url_get = f'{params["eve_esi_url"]}{route}{params_str}'

    mail = requests.get(url_get, headers=header).json()
    body = mail['body'].replace('/"', '"')
    subject = mail['subject']

    print(f'Тема последнего письма: {subject}')
    print(f'Текст последнего письма: {body}')
    print('-------------------------------------------------')
    # ret = input('Добавить это письмо в шаблоны? [да/нет]')
    # if ret in list_yes:
    #     db.add_mail(subject, body)


def set_new_auth_params():
    full_auth()
    validate_and_get_id()
    put_config()
    return


def add_log(log_message):
    time_now = datetime.datetime.now().strftime("%H:%M:%S")
    log_box.tag_config('time', foreground='red')
    log_box.insert(END, str(time_now), 'time')
    log_box.insert(END, ' : ' + log_message + '\n')
    log_box.see('end')


if __name__ == '__main__':
    # Основной раздел
    # config = {}
    auth_code = ''

    db = MainDatabase()

    characters_id_to_send = []
    unfinded_characters = []

    # блок статических данных для обращения к CCP
    params = {'callback_url': 'http://localhost:8000/',
              'login_server_base_url': 'login.eveonline.com',
              'response_type': 'code',
              'scopes': 'esi-wallet.read_character_wallet.v1%20esi-search.search_structures.v1%20esi-mail.send_mail.v1%20esi-mail.read_mail.v1%20esi-mail.organize_mail.v1',
              'state': 'test_api',
              'eve_esi_url': 'https://esi.evetech.net/latest',
              'authorization_code': '',
              'character_id': ''}

    config = get_config()

    try:
        # Проверим не просрочен ли токен
        check_token()

        # производим валидацию данных + узнаем id персонажа который авторизовался
        validate_and_get_id()
    except:
        print('Ошибка в данных авторизации, попробуйте ввести их заново')
        set_new_auth_params()

    # list_yes = ["yes", "y", "YES", "Y", "+", "Д", "ДА", "д", "да"]
    # list_no = ["no", "n", "NO", "N", "-", "Н", "НЕТ", "н", "нет"]

    window = Tk()
    window.title('Автоспамер :)')
    text_box = Text(window, height=10, width=70)
    text_box.grid(row=5, column=3, rowspan=6, padx=10)
    log_box = Text(window, height=10, width=70)
    log_box.grid(row=0, column=3, rowspan=6, padx=10)
    btn1 = Button(window, text='Добавить новые никнеймы из буфера обмена', command=add_new_nicknames)
    btn1.grid(column=0, row=0, padx=10, pady=5)
    btn2 = Button(window, text='Сформировать пакет никнеймов к отправке', command=gen_nickname_pack)
    btn2.grid(column=0, row=1, padx=10, pady=5)
    btn3 = Button(window, text='Сформировать пакет ненайденных через API никнеймов для ручной отправки',
                  command=gen_unfind_nickname_pack)
    btn3.grid(column=0, row=2, padx=10, pady=5)
    btn4 = Button(window, text='Отправить письма очередным 50 никнеймам через API', command=send_mail_api)
    btn4.grid(column=0, row=3, padx=10, pady=5)
    btn5 = Button(window, text='Отправить письмо конкретному получателю через API',
                  command=add_mail_one_nickname_window)
    btn5.grid(column=0, row=4, padx=10, pady=5)
    btn6 = Button(window, text='Выбрать текущий вариант текста письма для отправки', state='disable')
    btn6.grid(column=0, row=5, padx=10, pady=5)
    btn7 = Button(window, text='Добавить/изменить текст письма для отправки', command=add_mail_main_window)
    btn7.grid(column=0, row=6, padx=10, pady=5)
    btn8 = Button(window, text='Удалить вариант текста письма для отправки из базы', state='disable')
    btn8.grid(column=0, row=7, padx=10, pady=5)
    btn9 = Button(window, text='Получить текст последнего письма', state='disable')
    btn9.grid(column=0, row=8, padx=10, pady=5)
    btn10 = Button(window, text='Задать новые ClientID и Secret key', state='disable')
    btn10.grid(column=0, row=9, padx=10, pady=5)
    btn11 = Button(window, text='Выход', command=lambda: window.quit())
    btn11.grid(column=0, row=10, padx=10, pady=5)
    print_stats(db)
    add_log('Запуск программы')
    window.mainloop()

# Основное меню
# while True:
#     ret = input('---------------------------------\n'
#                 'Выберите действие:\n'
#                 '1) Добавить новые никнеймы из буфера обмена\n'
#                 '2) Сформировать пакет никнеймов к отправке\n'
#                 '3) Сформировать пакет ненайденных через API никнеймов для ручной отправки\n'
#                 '4) Отправить письма очередным 50 никнеймам через API\n'
#                 '5) Отправить письмо конкретному получателю через API\n'
#                 '6) Выбрать текущий вариант текста письма для отправки\n'
#                 '7) Добавить вариант текста письма для отправки в базу из буфера обмена\n'
#                 '8) Удалить вариант текста письма для отправки из базы\n'
#                 '9) Получить текст последнего письма\n'
#                 'k) Задать новые ClientID и Secret key\n'
#                 '0) Выход\n'
#                 'Ваш выбор: ')
#
#     if ret == '1':
#         add_new_nicknames()
#
#     elif ret == '2':
#         gen_nickname_pack()
#
#     elif ret == '3':
#         gen_unfind_nickname_pack()
#
#     elif ret == '4':
#         send_mail_api()
#
#     elif ret == '5':
#         send_mail_api_one_nickname()
#
#     elif ret == '6':
#         select_mail()
#
#     elif ret == '7':
#         add_mail()
#
#     elif ret == '8':
#         delete_mail()
#
#     elif ret == '9':
#         get_last_mail()
#
#     elif ret in ('k', 'K', 'к', 'К'):
#         set_new_auth_params()
#
#     elif ret == '0':
#         exit()
#
#     else:
#         continue
