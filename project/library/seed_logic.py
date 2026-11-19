# -*- coding: utf-8 -*-
"""Генерация тестовых данных для базы «Библиотека колледжа» (занятие 5).

Модуль не зависит от Django: build() возвращает словарь «таблица -> список строк».
Команда manage.py seed_data переносит эти строки в базу через ORM.
Данные детерминированы: одинаковые today, books, readers и seed дают одинаковый результат.
"""
import datetime as dt
import random

GENRES = [
    ("Роман", "Крупная прозаическая форма"),
    ("Повесть и рассказ", "Малая и средняя проза"),
    ("Поэзия", "Стихотворения и поэмы"),
    ("Учебник по математике и физике", "Учебные издания для СПО"),
    ("Учебник по информатике", "Учебные издания для СПО"),
    ("Учебник по экономике и праву", "Учебные издания для СПО"),
    ("Учебник по общественным и гуманитарным наукам", "Учебные издания для СПО"),
    ("Справочник и практикум", "Справочные и практические издания"),
]
# (фамилия, имя, отчество, год рождения)
CLASSIC_AUTHORS = [
    ("Толстой", "Лев", "Николаевич", 1828), ("Достоевский", "Фёдор", "Михайлович", 1821),
    ("Пушкин", "Александр", "Сергеевич", 1799), ("Лермонтов", "Михаил", "Юрьевич", 1814),
    ("Гоголь", "Николай", "Васильевич", 1809), ("Тургенев", "Иван", "Сергеевич", 1818),
    ("Чехов", "Антон", "Павлович", 1860), ("Булгаков", "Михаил", "Афанасьевич", 1891),
    ("Шолохов", "Михаил", "Александрович", 1905), ("Островский", "Николай", "Алексеевич", 1904),
    ("Некрасов", "Николай", "Алексеевич", 1821), ("Есенин", "Сергей", "Александрович", 1895),
    ("Маяковский", "Владимир", "Владимирович", 1893), ("Горький", "Максим", "", 1868),
]
# (название, индекс автора, жанр, число страниц)
CLASSICS = [
    ("Война и мир", 0, 0, 1274), ("Анна Каренина", 0, 0, 864), ("Преступление и наказание", 1, 0, 608),
    ("Идиот", 1, 0, 640), ("Евгений Онегин", 2, 2, 224), ("Капитанская дочка", 2, 1, 192),
    ("Герой нашего времени", 3, 0, 224), ("Мёртвые души", 4, 0, 352), ("Отцы и дети", 5, 0, 320),
    ("Рассказы", 6, 1, 416), ("Мастер и Маргарита", 7, 0, 480), ("Тихий Дон", 8, 0, 1344),
    ("Как закалялась сталь", 9, 0, 384), ("Кому на Руси жить хорошо", 10, 2, 288),
    ("Стихотворения", 11, 2, 320), ("Стихотворения и поэмы", 12, 2, 352), ("На дне", 13, 1, 160),
    ("Бесы", 1, 0, 736),
]
SUBJECTS = [  # (дисциплина, индекс жанра)
    ("Математика", 3), ("Физика", 3), ("Дискретная математика", 3), ("Теория вероятностей", 3), ("Электротехника", 3),
    ("Информатика", 4), ("Основы программирования", 4), ("Базы данных", 4), ("Компьютерные сети", 4),
    ("Операционные системы", 4), ("Информационная безопасность", 4), ("Веб-разработка", 4), ("Основы алгоритмизации", 4),
    ("Экономика организации", 5), ("Бухгалтерский учёт", 5), ("Менеджмент", 5), ("Основы права", 5),
    ("Статистика", 5), ("Маркетинг", 5), ("Финансы и кредит", 5),
    ("История России", 6), ("Русский язык и культура речи", 6), ("Английский язык", 6),
    ("Обществознание", 6), ("Основы философии", 6), ("Психология общения", 6), ("Охрана труда", 6),
    ("Документационное обеспечение управления", 6), ("Метрология", 3), ("Химия", 3),
]
KINDS = [("учебник для СПО", None), ("практикум", 7), ("сборник задач", 7), ("справочник", 7)]
PUBLISHERS = ["Просвещение", "Академия", "Дрофа", "Эксмо", "АСТ", "Питер", "КноРус"]
SURN = ["Орлов", "Белов", "Волков", "Громов", "Дьячков", "Егоров", "Жуков", "Зайцев", "Исаев", "Кузнецов", "Лебедев",
        "Макаров", "Никитин", "Осипов", "Павлов", "Рябов", "Сергеев", "Титов", "Ушаков", "Фомин", "Харитонов",
        "Цветков", "Чернов", "Шестаков", "Щербаков", "Юдин", "Яковлев", "Антонов", "Борисов", "Васильев", "Герасимов"]
MN = ["Александр", "Андрей", "Борис", "Виктор", "Дмитрий", "Евгений", "Игорь", "Константин", "Михаил", "Николай", "Олег", "Сергей"]
MP = ["Александрович", "Андреевич", "Борисович", "Викторович", "Дмитриевич", "Евгеньевич", "Игоревич", "Михайлович", "Николаевич", "Сергеевич"]
FN = ["Анна", "Елена", "Ирина", "Мария", "Наталья", "Ольга", "Светлана", "Татьяна", "Юлия", "Екатерина"]
FP = ["Александровна", "Андреевна", "Викторовна", "Дмитриевна", "Игоревна", "Михайловна", "Николаевна", "Сергеевна"]
RS_M = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузьмин", "Попов", "Соколов", "Лебедев", "Козлов", "Новиков",
        "Морозов", "Андреев", "Семёнов", "Егоров", "Захаров", "Беляев", "Тарасов", "Гусев", "Комаров", "Крылов", "Суслов", "Ершов"]
GROUPS = ["ИС-21", "ИС-22", "ИС-31", "БУ-21", "БУ-22", "ЭК-21", "ЭК-32", "ПО-21", "ПО-31", "ТМ-22"]


def isbn13(rng, used):
    while True:
        body = "9785" + "".join(str(rng.randint(0, 9)) for _ in range(8))
        s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(body))
        check = (10 - s % 10) % 10
        full = body + str(check)
        txt = f"{full[:3]}-{full[3]}-{full[4:9]}-{full[9:12]}-{full[12]}"
        if txt not in used:
            used.add(txt)
            return txt


def build(today, books=120, readers=100, seed=42):
    rng = random.Random(seed)
    d = dt.timedelta
    T = {k: [] for k in ["genre", "author", "book", "bookauthor", "copy", "reader", "staff", "settings", "reservation",
                          "loan", "renewal", "fine", "notification", "favorite"]}
    users = []  # (username, роль, индекс читателя или None)
    # ---- настройки
    st = dict(id=1, fine_per_day=5, loan_days=14, renewal_days=14, max_renewals=1, reservation_hold_days=3, reminder_days=2)
    T["settings"].append(st)
    # ---- жанры
    for i, (n, ds) in enumerate(GENRES, 1):
        T["genre"].append(dict(id=i, name=n, description=ds))
    # ---- авторы
    for i, (l, f, m, y) in enumerate(CLASSIC_AUTHORS, 1):
        T["author"].append(dict(id=i, last_name=l, first_name=f, middle_name=m, birth_year=y))
    seen = set((a["last_name"], a["first_name"], a["middle_name"], a["birth_year"]) for a in T["author"])
    pool = []
    while len(pool) < 45:
        key = (rng.choice(SURN), rng.choice(MN), rng.choice(MP), rng.randint(1950, 1985))
        if key in seen: continue
        seen.add(key)
        T["author"].append(dict(id=len(T["author"]) + 1, last_name=key[0], first_name=key[1], middle_name=key[2], birth_year=key[3]))
        pool.append(len(T["author"]))
    # ---- книги
    used_isbn = set()
    titles = []
    for t, a, g, p in CLASSICS[:books]:
        titles.append((t, [a + 1], g + 1, p, True))
    k = 0
    combos = [(s, g, kind, kg) for kind, kg in KINDS for s, g in SUBJECTS]
    while len(titles) < books:
        s, g, kind, kg = combos[k % len(combos)]
        ed = k // len(combos) + 1
        name = f"{s}: {kind}" + (f" (издание {ed + 1})" if ed > 1 else "")
        titles.append((name, rng.sample(pool, rng.choice([1, 1, 2, 3])), (kg if kg is not None else g) + 1, rng.randint(96, 640), False))
        k += 1
    for bid, (t, auths, g, pages, classic) in enumerate(titles, 1):
        T["book"].append(dict(id=bid, title=t, genre_id=g, isbn=isbn13(rng, used_isbn),
                              publisher=rng.choice(PUBLISHERS), year_published=rng.randint(2008 if classic else 2015, 2024),
                              pages=pages, description=(f"Издание из школьной и студенческой программы: «{t}»." if classic else f"Учебное издание для студентов СПО: {t}."),
                              created_at=dt.datetime.combine(today - d(days=rng.randint(130, 800)), dt.time(10, 0))))
        for pos, a in enumerate(auths, 1):
            T["bookauthor"].append(dict(id=len(T["bookauthor"]) + 1, book_id=bid, author_id=a, position=pos))
    # ---- экземпляры
    inv = 100000
    for b in T["book"]:
        n = rng.randint(2, 4) if b["id"] <= len(CLASSICS) else rng.randint(2, 5)
        for _ in range(n):
            inv += 1
            r = rng.random()
            cond = "good" if r < 0.82 else ("worn" if r < 0.96 else "damaged")
            T["copy"].append(dict(id=len(T["copy"]) + 1, book_id=b["id"], inventory_number=f"{inv:06d}", status="in_stock",
                                  condition=cond, shelf_location=f"Ст. {rng.randint(1, 12)}, пол. {rng.randint(1, 5)}",
                                  acquired_date=today - d(days=rng.randint(200, 2500)), written_off_date=None))
    for c in rng.sample(T["copy"], max(1, len(T["copy"]) // 50)):
        c["status"], c["written_off_date"], c["condition"] = "written_off", today - d(days=rng.randint(5, 200)), "damaged"
    # ---- сотрудники
    for i, (fio, role, pos, uname) in enumerate([("Смирнова Ирина Павловна", "admin", "Администратор системы", "admin"),
                                                  ("Петрова Анна Ивановна", "librarian", "Библиотекарь", "librarian1"),
                                                  ("Соколов Дмитрий Андреевич", "librarian", "Библиотекарь", "librarian2")], 1):
        users.append((uname, role, None))
        T["staff"].append(dict(id=i, user_idx=len(users), full_name=fio, role=role, position=pos))
    librarians = [s["id"] for s in T["staff"] if s["role"] == "librarian"]
    # ---- читатели
    used = set()
    for i in range(readers):
        male = rng.random() < 0.5
        while True:
            fio = (rng.choice(RS_M) + ("" if male else "а"), rng.choice(MN if male else FN), rng.choice(MP if male else FP))
            if fio not in used: used.add(fio); break
        card = f"{200001 + i}"
        rd = dict(id=i + 1, user_idx=None, card_number=card, full_name=" ".join(fio), group_name=rng.choice(GROUPS),
                  phone=f"+7 9{rng.randint(0, 9)}{rng.randint(0, 9)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
                  email=(f"reader{card}@example.com" if rng.random() < 0.5 else ""),
                  registered_at=today - d(days=rng.randint(130, 900)), is_blocked=False, block_reason="")
        if i < 12:
            users.append((f"reader_{card}", "reader", i + 1)); rd["user_idx"] = len(users)
        T["reader"].append(rd)
    # ---- кандидаты на выдачи по экземплярам
    ld, rdays = st["loan_days"], st["renewal_days"]
    win = today - d(days=120)
    cand = []
    for c in T["copy"]:
        if c["status"] == "written_off": continue
        cur = win + d(days=rng.randint(0, 40))
        while cur < today - d(days=1):
            if rng.random() > 0.26:
                cur += d(days=rng.randint(7, 30)); continue
            issued, due, ren = cur, cur + d(days=ld), []
            if rng.random() < 0.12:
                nd = due + d(days=rdays)
                ren.append((issued + d(days=rng.randint(3, ld - 1)), due, nd)); due = nd
            typ = rng.choices(["ontime", "late", "open"], [0.60, 0.17, 0.23])[0]
            if typ == "open" and issued < today - d(days=ld + 8):
                typ = "ontime" if rng.random() < 0.85 else "late"   # давняя выдача редко остаётся открытой
            elif typ == "open" and issued < today - d(days=ld) and rng.random() < 0.75:
                typ = "ontime"                                       # просроченных на руках должно быть немного
            if typ == "ontime": ret = issued + d(days=rng.randint(2, (due - issued).days))
            elif typ == "late": ret = due + d(days=rng.randint(1, 25))
            else: ret = None
            if ret is not None and ret > today: ret = None
            cand.append(dict(copy=c, issued=issued, due=due, ret=ret, ren=ren))
            if ret is None: break
            cur = ret + d(days=rng.randint(0, 25))
    cand.sort(key=lambda x: (x["issued"], x["copy"]["id"]))
    # ---- назначение читателей с проверкой блокировки на дату выдачи
    acc = {r["id"]: [] for r in T["reader"]}
    def blocked_on(rid, day):
        for l in acc[rid]:
            if l["due"] < day and (l["ret"] is None or l["ret"] >= day): return True
            f = l.get("fine")
            if f and l["ret"] <= day and (f["paid_at"] is None or f["paid_at"] > day): return True
        return False
    loans = []
    for cdt in cand:
        for _ in range(10):
            rid = rng.choice(T["reader"])["id"]
            if T["reader"][rid - 1]["registered_at"] <= cdt["issued"] and not blocked_on(rid, cdt["issued"]):
                break
        else:
            continue
        cdt["reader"] = rid
        if cdt["ret"] is not None and cdt["ret"] > cdt["due"]:
            days = (cdt["ret"] - cdt["due"]).days
            age = (today - cdt["ret"]).days
            paid = rng.random() < (0.97 if age > 30 else 0.8 if age > 14 else 0.4)
            pa = min(today, cdt["ret"] + d(days=rng.randint(0, 12))) if paid else None
            cdt["fine"] = dict(days=days, paid_at=pa)
        acc[rid].append(cdt); loans.append(cdt)
    loans.sort(key=lambda x: (x["issued"], x["copy"]["id"]))
    for i, l in enumerate(loans, 1): l["id"] = i
    # ---- резервы (нужны до записи выдач: ссылка Loan.reservation)
    book_copies = {}
    for c in T["copy"]: book_copies.setdefault(c["book_id"], []).append(c)
    for l in loans:
        if l["ret"] is None: l["copy"]["status"] = "on_loan"
    def cur_blocked(rid):
        for l in acc[rid]:
            if l["ret"] is None and l["due"] < today: return True
            f = l.get("fine")
            if f and (f["paid_at"] is None): return True
        return False
    free_readers = [r["id"] for r in T["reader"] if not cur_blocked(r["id"])]
    res = []
    def add_res(**kw):
        res.append(kw); return kw
    # очередь на книги, все экземпляры которых на руках
    allout = [b for b, cs in book_copies.items() if all(c["status"] in ("on_loan", "written_off") for c in cs) and any(c["status"] == "on_loan" for c in cs)]
    for b in rng.sample(allout, min(8, len(allout))):
        for rid in rng.sample(free_readers, min(rng.randint(1, 3), len(free_readers))):
            add_res(reader_id=rid, book_id=b, created_at=dt.datetime.combine(today - d(days=rng.randint(1, 10)), dt.time(rng.randint(8, 17), rng.randint(0, 59))),
                    status="active", assigned=None, ready_at=None, hold_until=None, loan=None)
    # отложенные книги
    avail = [b for b, cs in book_copies.items() if any(c["status"] == "in_stock" for c in cs)]
    taken = set((r["reader_id"], r["book_id"]) for r in res)
    for b in rng.sample(avail, min(4, len(avail))):
        rid = rng.choice(free_readers)
        if (rid, b) in taken: continue
        taken.add((rid, b))
        cp = rng.choice([c for c in book_copies[b] if c["status"] == "in_stock"]); cp["status"] = "reserved"
        ra = today - d(days=rng.randint(0, 2))
        add_res(reader_id=rid, book_id=b, created_at=dt.datetime.combine(ra - d(days=rng.randint(1, 6)), dt.time(12, 0)), status="ready",
                assigned=cp, ready_at=ra, hold_until=ra + d(days=st["reservation_hold_days"]), loan=None)
    # выполненные: по закрытым выдачам вовремя
    ontime = [l for l in loans if l["ret"] is not None and "fine" not in l]
    for l in rng.sample(ontime, min(6, len(ontime))):
        ra = l["issued"] - d(days=1)
        r_ = add_res(reader_id=l["reader"], book_id=l["copy"]["book_id"], created_at=dt.datetime.combine(ra - d(days=rng.randint(1, 8)), dt.time(11, 0)),
                     status="fulfilled", assigned=l["copy"], ready_at=ra, hold_until=ra + d(days=3), loan=l)
        l["res"] = r_
    # истёкшие и отменённые
    for st_, n in (("expired", 3), ("cancelled", 2)):
        for _ in range(n):
            rid, b = rng.choice(free_readers), rng.choice(list(book_copies))
            if (rid, b) in taken: continue
            ra = today - d(days=rng.randint(8, 15))
            if st_ == "expired":
                add_res(reader_id=rid, book_id=b, created_at=dt.datetime.combine(ra - d(days=3), dt.time(10, 0)), status="expired",
                        assigned=rng.choice(book_copies[b]), ready_at=ra, hold_until=ra + d(days=3), loan=None)
            else:
                add_res(reader_id=rid, book_id=b, created_at=dt.datetime.combine(ra, dt.time(10, 0)), status="cancelled", assigned=None, ready_at=None, hold_until=None, loan=None)
    res.sort(key=lambda x: x["created_at"])
    for i, r_ in enumerate(res, 1):
        r_["id"] = i
        T["reservation"].append(dict(id=i, reader_id=r_["reader_id"], book_id=r_["book_id"], created_at=r_["created_at"], status=r_["status"],
                                     assigned_copy_id=(r_["assigned"]["id"] if r_["assigned"] else None), ready_at=r_["ready_at"], hold_until=r_["hold_until"]))
    # ---- выдачи, продления, штрафы
    for l in loans:
        cond = ""
        if l["ret"] is not None:
            x = rng.random(); cond = "good" if x < 0.9 else ("worn" if x < 0.97 else "damaged")
            if cond == "damaged": l["copy"]["condition"] = "damaged"
        T["loan"].append(dict(id=l["id"], copy_id=l["copy"]["id"], reader_id=l["reader"], issued_by_id=rng.choice(librarians),
                              received_by_id=(rng.choice(librarians) if l["ret"] else None),
                              reservation_id=(l["res"]["id"] if l.get("res") else None), issued_at=l["issued"], due_date=l["due"],
                              returned_at=l["ret"], return_condition=cond))
        for ra, pv, nw in l["ren"]:
            T["renewal"].append(dict(id=len(T["renewal"]) + 1, loan_id=l["id"], renewed_at=ra, previous_due_date=pv, new_due_date=nw))
        f = l.get("fine")
        if f:
            T["fine"].append(dict(id=len(T["fine"]) + 1, loan_id=l["id"], days_overdue=f["days"], rate_per_day=st["fine_per_day"],
                                  amount=f["days"] * st["fine_per_day"], status="paid" if f["paid_at"] else "unpaid", accrued_at=l["ret"],
                                  paid_at=f["paid_at"], accepted_by_id=(rng.choice(librarians) if f["paid_at"] else None)))
    # ---- блокировка читателей на сегодня
    for r in T["reader"]:
        reasons = []
        ov = [l for l in acc[r["id"]] if l["ret"] is None and l["due"] < today]
        if ov:
            l = max(ov, key=lambda x: (today - x["due"]).days)
            reasons.append(f"Просрочка: «{T['book'][l['copy']['book_id'] - 1]['title']}», {(today - l['due']).days} дн.")
        unp = sum(l["fine"]["days"] * st["fine_per_day"] for l in acc[r["id"]] if l.get("fine") and l["fine"]["paid_at"] is None)
        if unp: reasons.append(f"Не оплачен штраф: {unp} руб.")
        if reasons: r["is_blocked"], r["block_reason"] = True, "; ".join(reasons)[:200]
    # ---- уведомления
    now = dt.datetime.combine(today, dt.time(8, 0))
    for l in loans:
        if l["ret"] is None and 0 <= (l["due"] - today).days <= st["reminder_days"]:
            T["notification"].append(dict(reader_id=l["reader"], kind="due_soon", text=f"Срок возврата книги «{T['book'][l['copy']['book_id'] - 1]['title']}» — {l['due']:%d.%m.%Y}", created_at=now, is_read=rng.random() < 0.3, loan_id=l["id"], reservation_id=None))
    for r_ in T["reservation"]:
        if r_["status"] == "ready":
            T["notification"].append(dict(reader_id=r_["reader_id"], kind="reservation_ready", text=f"Книга «{T['book'][r_['book_id'] - 1]['title']}» отложена до {r_['hold_until']:%d.%m.%Y}", created_at=now, is_read=False, loan_id=None, reservation_id=r_["id"]))
    for r in T["reader"]:
        if r["is_blocked"]:
            T["notification"].append(dict(reader_id=r["id"], kind="blocked", text=f"Выдача заблокирована. {r['block_reason']}", created_at=now, is_read=rng.random() < 0.5, loan_id=None, reservation_id=None))
    for i, n in enumerate(T["notification"], 1): n["id"] = i
    # ---- избранное
    pairs = set()
    for r in rng.sample(T["reader"], min(25, len(T["reader"]))):
        for b in rng.sample(T["book"], rng.randint(2, 4)):
            if (r["id"], b["id"]) in pairs: continue
            pairs.add((r["id"], b["id"]))
            T["favorite"].append(dict(id=len(T["favorite"]) + 1, reader_id=r["id"], book_id=b["id"], added_at=dt.datetime.combine(today - d(days=rng.randint(0, 60)), dt.time(rng.randint(8, 20), rng.randint(0, 59)))))
    return T, users


if __name__ == "__main__":
    T, u = build(dt.date(2026, 11, 13))
    print({k: len(v) for k, v in T.items()}, len(u))
