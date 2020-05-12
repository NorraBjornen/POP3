import re
import socket
import ssl
import base64
import sys

re_boundary = r'boundary="(.+?)"'


def request(sock, req):
    sock.send((req + '\n').encode())
    recv_data = sock.recv(65535).decode()
    return recv_data


def connect(client, addr, user, password):
    client.connect(addr)
    client = ssl.wrap_socket(client)
    client.settimeout(1)
    client.recv(1024).decode()
    request(client, 'USER ' + user)
    request(client, 'PASS ' + password)
    return client


def main(host_addr, port, user_name, password, number=None):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client = connect(client, (host_addr, port), user_name, password)
            if number is None:
                print(f"Количество писем в Вашем почтовом ящике: {request(client, 'STAT').split()[1]}")
                number = read_number()
                print(f"Получение письма №{number}...")

            request(client, f'RETR {number}')
            # print(request(client, 'TOP 1 10'))

            full_mail = ""
            while True:
                try:
                    full_mail += client.recv(4100).decode()
                except socket.timeout:
                    break

            parse(full_mail, client)
    except Exception as e:
        if str(e) == "'Content-Type'":
            main(host_addr, port, user_name, password, number)
        else:
            print(e)


def read_number():
    print("Введите номер письма, с которым Вы хотите работать:")
    number = input()
    if not number.isdigit():
        print("Некорректный номер")
        return read_number()
    return number


def parse(full_mail, client):
    lines = full_mail.split("\r\n")

    i = 0
    for line in lines:
        if line == "":
            break
        i += 1

    headers_str = "\r\n".join(lines[:i])
    content_str = "\r\n".join(lines[i + 1:])

    prev = ""
    prev_header = ""
    headers = []
    for line in lines[:i]:
        if line == "":
            continue

        if line[0].isalpha():
            if prev_header != "":
                headers.append((prev_header, prev))

            ind = line.index(":")
            header = line[:ind]
            content = line[ind + 2:]
            prev_header = header
            prev = content
        else:
            prev += "\n" + line

    if prev_header != "":
        headers.append((prev_header, prev))

    d = dict()
    for a, b in headers:
        d[a] = b

    content_type = d["Content-Type"]

    just_text = True

    if "multipart" in content_type:
        if "alternative" in content_type:
            just_text = True
        elif "mixed" in content_type:
            just_text = False

    main_boundary = '--' + re.findall(re_boundary, content_type)[0]

    result = []

    if just_text:
        result = content_str.split(main_boundary)[1:-1]
    else:
        content_parts = content_str.split(main_boundary)[1:-1]
        for part in content_parts:
            if "multipart" in part:
                sub_boundary = '--' + re.findall(re_boundary, part)[0]
                sub_parts = part.split(sub_boundary)[1:-1]
                result += sub_parts
            else:
                result.append(part)

    r = []

    for part in result:
        if "Content-Type: text" in part:
            p = part.split("\r\n")[1:-1]
            i = 0
            for line in p:
                if line == "":
                    break
                i += 1

            content = "\n".join(p[i + 1:])

            if "Content-Transfer-Encoding" in part:
                content = base64.b64decode(content).decode()
            r.append(content)
        else:
            r.append(part)

    print("Письмо получено")
    print(f"Число видов содержаний: {len(r)}")
    if not just_text:
        print("\tТакже присутствуют вложения")

    handle_cmd(full_mail, d, r, headers_str, content_str, client)


def handle_cmd(lines, headers_dict, contents, headers_str, content_str, client):
    while True:
        cmd = input("Введите команду: ")
        if cmd == "q":
            break

        if cmd == "s":
            print(lines)
            with open("mail", "w+") as f:
                f.write(lines)
            continue

        try:
            cmd, arg = cmd.split()
            if cmd == "s":
                if arg == "h":
                    print(headers_str)
                elif arg == "c":
                    print(content_str)
            elif cmd == "h":
                print(headers_dict[arg])
            elif cmd == "c":
                print(contents[int(arg)])
            elif cmd == "t":
                print(headers_str)
                print("\n".join(content_str.split("\r\n")[:int(arg)]))
        except Exception as e:
            print("Некорректно введена команда. Код ошибки: " + str(e))

    print(request(client, 'QUIT'))


def print_help():
    print("Запуск приложения:")
    print("\tpython mail.py [доменное имя почтового сервера] [порт] [имя пользователя] [пароль]")
    print("\nПример запуска:\n\tpython mail.py pop.mail.ru 995 user@mail.ru password")
    print("\nКоманды пользователя:")
    s = """s                       - показать письмо полностью и сохранить в файл                                  (show)
        s h                     - показать заголовки письма                                                     (show headers)
        s c                     - показать сообщение письма                                                     (show content)
        h [название заголовка]  - показать значение указанного заголовка                                        (header n)
        c [номер содержимого]   - показать содержимое по указанному номеру (без заголовков типов сообщений)     (content n)
        t [количество строк]    - показать заголовки и указанное количество строк сообщения (Аналог TOP)        (top n)
        q                       - завершение сессии и выход                                                     (quit)
        """
    print("\t\t" + s)


if __name__ == "__main__":
    if len(sys.argv) != 5 or (len(sys.argv) == 2 and sys.argv[1] == "-h"):
        print_help()
    else:
        main(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
