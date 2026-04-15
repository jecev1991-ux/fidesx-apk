#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║         FIDESx v9  —  Deriv Auto Trading  [ANDROID]              ║
║   FASE 1: N Losses Reais → FASE 2: Alternâncias L/W Virtuais    ║
║   v9: Copiar API · Token-Lock · Campos Adaptativos              ║
╚══════════════════════════════════════════════════════════════════╝
Dependências Android (buildozer.spec):
    kivy==2.2.0, websocket-client, requests
"""

import os, sys, json, threading, hashlib, time, ssl, datetime, base64 as _b64
from functools import partial

try:
    from urllib.request import urlopen, Request as _URLRequest
    _URL_OK = True
except ImportError:
    _URL_OK = False

try:
    import websocket as _wslib
    WS_OK = True
except ImportError:
    WS_OK = False

import kivy
kivy.require("2.2.0")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.utils import get_color_from_hex as hex_c

# ═══════════════════════ TEMA ═══════════════════════════════════════
C_BG      = hex_c("#06090f")
C_PANEL   = hex_c("#0b0f1a")
C_CARD    = hex_c("#10151f")
C_INPUT   = hex_c("#141c28")
C_BORDER  = hex_c("#1e2a3a")
C_GOLD    = hex_c("#e8b84b")
C_GREEN   = hex_c("#00e676")
C_RED     = hex_c("#ff3d5a")
C_CYAN    = hex_c("#00ffe0")
C_WHITE   = hex_c("#dce8f5")
C_GRAY    = hex_c("#4a5a6e")
C_STOP    = hex_c("#ff6b35")

DERIV_WS = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

MERCADOS = [
    "1HZ10V","1HZ25V","1HZ50V","1HZ75V","1HZ100V",
    "R_10","R_25","R_50","R_75","R_100",
]

TIPOS_CONTRATO = [
    "DIGITOVER","DIGITUNDER","DIGITODD","DIGITEVEN",
    "DIGITMATCH","DIGITDIFF","CALL","PUT",
]

DEFAULT = {
    "mercado":       "1HZ10V",
    "contrato":      "DIGITOVER",
    "barreira":      "3",
    "duracao":       "1",
    "stake":         "1.00",
    "win_amount":    "0.35",
    "profit_alvo":   "10.00",
    "stop_loss":     "100.00",
    "gale_mult":     "2.0",
    "losses_fase1":  "3",
    "nivel_fase2":   "1",
    "wins_pausa":    "3",
    "minutos_pausa": "5",
    "seq_f1":        "",
    "copy_token":    "",
    "api_token":     "",
}

# ═══════════════════════ LICENÇA ════════════════════════════════════
LICENCA_EMBUTIDA      = ""
_CHAVE_SECRETA_LIC    = "G4_GUERRA_SECRET_2025"
_LICENCA_FILE         = "licenca_g4.lic"
_BLACKLIST_FILE       = "blacklist_g4.txt"
_REVOGACAO_REMOTA_URL = "https://raw.githubusercontent.com/jecev1991-ux/licencas-fidex/refs/heads/main/Revogados.txt"
_CACHE_REMOTA         = set()
_CACHE_REMOTA_LOCK    = threading.Lock()

import json as _json_lic

def _lic_assinar(p64):
    return hashlib.sha256((p64 + _CHAVE_SECRETA_LIC).encode()).hexdigest()[:16].upper()

def _lic_revogada(codigo):
    digest = hashlib.sha256(codigo.strip().encode()).hexdigest()[:20].upper()
    if os.path.exists(_BLACKLIST_FILE):
        with open(_BLACKLIST_FILE, "r", encoding="utf-8") as f:
            if digest in {l.strip() for l in f if l.strip()}:
                return True
    with _CACHE_REMOTA_LOCK:
        return digest in _CACHE_REMOTA

def validar_licenca(codigo):
    codigo = codigo.strip()
    if not codigo:
        return None, "Código vazio"
    if _lic_revogada(codigo):
        return None, "Licença revogada"
    try:
        partes = codigo.rsplit("-", 1)
        if len(partes) != 2:
            return None, "Formato inválido"
        dados_b64, sig = partes
        if _lic_assinar(dados_b64) != sig:
            return None, "Assinatura inválida"
        payload = _json_lic.loads(_b64.b64decode(dados_b64 + "==").decode())
        plano = payload.get("plano", "").upper()
        if plano not in ("STANDARD", "PREMIUM", "ADMIN"):
            return None, "Plano desconhecido"
        if not payload.get("vitalicia", False):
            exp_str = payload.get("expira", "")
            if exp_str:
                exp_dt = datetime.datetime.fromisoformat(exp_str)
                if datetime.datetime.now() > exp_dt:
                    return None, f"Expirada em {exp_str[:10]}"
        return plano, None
    except Exception as e:
        return None, f"Erro: {e}"

def _lic_carregar():
    if LICENCA_EMBUTIDA:
        return LICENCA_EMBUTIDA
    try:
        with open(_LICENCA_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def _lic_salvar(codigo):
    try:
        with open(_LICENCA_FILE, "w", encoding="utf-8") as f:
            f.write(codigo.strip())
    except Exception:
        pass

def _cfg_carregar():
    try:
        with open("fidesx_cfg.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _cfg_salvar(cfg):
    try:
        with open("fidesx_cfg.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ═══════════════════════ WIDGETS HELPER ═════════════════════════════
def dark_btn(text, color=None, height=dp(48), font_size=sp(14)):
    c = color or C_GOLD
    btn = Button(
        text=text,
        size_hint_y=None,
        height=height,
        font_size=font_size,
        color=C_BG,
        background_normal="",
        background_color=c,
        bold=True,
    )
    return btn

def dark_input(hint="", text="", password=False, multiline=False):
    inp = TextInput(
        hint_text=hint,
        text=text,
        password=password,
        multiline=multiline,
        size_hint_y=None,
        height=dp(42),
        background_normal="",
        background_active="",
        background_color=C_INPUT,
        foreground_color=C_WHITE,
        hint_text_color=C_GRAY,
        cursor_color=C_GOLD,
        font_size=sp(13),
        padding=[dp(12), dp(10)],
    )
    return inp

def lbl(text, color=None, size=sp(13), bold=False, halign="left"):
    return Label(
        text=text,
        color=color or C_WHITE,
        font_size=size,
        bold=bold,
        halign=halign,
        size_hint_y=None,
        height=dp(28),
        text_size=(None, None),
    )

def separator(color=C_BORDER):
    w = Widget(size_hint_y=None, height=dp(1))
    with w.canvas:
        Color(*color)
        w._rect = Rectangle(size=w.size, pos=w.pos)
    w.bind(size=lambda i, v: setattr(i._rect, "size", v),
           pos=lambda i, v: setattr(i._rect, "pos", v))
    return w

# ═══════════════════════ BOT CORE ═══════════════════════════════════
class FIDESxBot:
    def __init__(self, cfg, log_cb, balance_cb, stop_cb):
        self.cfg         = dict(DEFAULT)
        self.cfg.update(cfg)
        self.log_cb      = log_cb
        self.balance_cb  = balance_cb
        self.stop_cb     = stop_cb
        self.rodando     = False
        self.ws          = None
        self.msgs        = []
        self._stop_req   = False
        self.balance     = 0.0
        self.lucro_total = 0.0
        self.losses_f1   = 0
        self.wins_pausa  = 0
        self.em_pausa    = False
        self.stake_atual = float(self.cfg.get("stake", "1.00"))

    def log(self, msg, tag="info"):
        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        linha = f"[{ts}] {msg}"
        self.msgs.append(linha)
        if len(self.msgs) > 300:
            self.msgs = self.msgs[-200:]
        Clock.schedule_once(lambda dt: self.log_cb(linha, tag), 0)

    def iniciar(self):
        if self.rodando:
            return
        self.rodando   = True
        self._stop_req = False
        threading.Thread(target=self._run_ws, daemon=True).start()

    def parar(self):
        self._stop_req = True
        self.rodando   = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

    def _run_ws(self):
        token = self.cfg.get("api_token", "").strip()
        if not token:
            self.log("❌ Token API não configurado!", "error")
            Clock.schedule_once(lambda dt: self.stop_cb(), 0)
            return
        self.log("🔌 Conectando à Deriv...", "info")

        def on_open(ws):
            self.log("✅ Conectado! Autenticando...", "ok")
            ws.send(json.dumps({"authorize": token}))

        def on_message(ws, msg):
            if self._stop_req:
                ws.close()
                return
            try:
                self._handle(ws, json.loads(msg))
            except Exception as e:
                self.log(f"⚠ Erro: {e}", "warn")

        def on_error(ws, err):
            self.log(f"❌ WS Erro: {err}", "error")

        def on_close(ws, code, reason):
            self.log(f"🔌 Desconectado ({code})", "warn")
            self.rodando = False
            Clock.schedule_once(lambda dt: self.stop_cb(), 0)

        try:
            self.ws = _wslib.WebSocketApp(
                DERIV_WS,
                on_open=on_open, on_message=on_message,
                on_error=on_error, on_close=on_close,
            )
            self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        except Exception as e:
            self.log(f"❌ Falha: {e}", "error")
            self.rodando = False
            Clock.schedule_once(lambda dt: self.stop_cb(), 0)

    def _handle(self, ws, data):
        t = data.get("msg_type", "")
        if t == "authorize":
            if data.get("error"):
                self.log(f"❌ Auth: {data['error']['message']}", "error")
                ws.close()
                return
            info = data.get("authorize", {})
            self.balance = float(info.get("balance", 0))
            self.log(f"✅ Autenticado! Saldo: ${self.balance:.2f}", "ok")
            Clock.schedule_once(lambda dt: self.balance_cb(self.balance), 0)
            ws.send(json.dumps({"balance": 1, "subscribe": 1}))
            self._comprar(ws)

        elif t == "buy":
            if data.get("error"):
                self.log(f"❌ Compra: {data['error']['message']}", "error")
            else:
                b = data.get("buy", {})
                self.log(f"📈 Contrato #{b.get('contract_id','?')} | ${b.get('buy_price','?')}", "trade")

        elif t == "proposal_open_contract":
            poc = data.get("proposal_open_contract", {})
            if poc.get("is_sold"):
                self._processar_resultado(ws, float(poc.get("profit", 0)))

        elif t == "balance":
            self.balance = float(data.get("balance", {}).get("balance", self.balance))
            Clock.schedule_once(lambda dt: self.balance_cb(self.balance), 0)

    def _comprar(self, ws):
        if self._stop_req or self.em_pausa:
            return
        c   = self.cfg
        par = {
            "contract_type": c.get("contrato", "DIGITOVER"),
            "symbol":        c.get("mercado",  "1HZ10V"),
            "duration":      int(c.get("duracao", "1")),
            "duration_unit": "t",
            "currency":      "USD",
            "amount":        self.stake_atual,
            "basis":         "stake",
        }
        ct = c.get("contrato", "")
        if ct in ("DIGITOVER","DIGITUNDER","DIGITMATCH","DIGITDIFF"):
            par["barrier"] = c.get("barreira", "3")
        ws.send(json.dumps({"buy": 1, "price": self.stake_atual, "parameters": par, "subscribe": 1}))

    def _processar_resultado(self, ws, profit):
        ganhou       = profit > 0
        c            = self.cfg
        profit_alvo  = float(c.get("profit_alvo", "10.00"))
        stop_loss    = float(c.get("stop_loss",   "100.00"))
        stake_base   = float(c.get("stake",        "1.00"))
        gale_mult    = float(c.get("gale_mult",    "2.0"))
        losses_max   = int(c.get("losses_fase1",   "3"))
        wins_max     = int(c.get("wins_pausa",     "3"))
        mins_pausa   = int(c.get("minutos_pausa",  "5"))

        self.lucro_total += profit
        emoji = "✅" if ganhou else "❌"
        self.log(f"{emoji} {'WIN' if ganhou else 'LOSS'} | P&L: {profit:+.2f} | Total: {self.lucro_total:+.2f}",
                 "ok" if ganhou else "error")

        if self.lucro_total >= profit_alvo:
            self.log(f"🎯 PROFIT ALVO atingido! +${self.lucro_total:.2f}", "ok")
            self.parar()
            Clock.schedule_once(lambda dt: self.stop_cb(), 0)
            return

        if self.lucro_total <= -stop_loss:
            self.log(f"🛑 STOP LOSS atingido! ${self.lucro_total:.2f}", "error")
            self.parar()
            Clock.schedule_once(lambda dt: self.stop_cb(), 0)
            return

        if ganhou:
            self.stake_atual = stake_base
            self.losses_f1   = 0
            self.wins_pausa += 1
            if self.wins_pausa >= wins_max:
                self.log(f"⏸ Pausa {mins_pausa} min após {wins_max} wins", "warn")
                self.em_pausa   = True
                self.wins_pausa = 0
                Clock.schedule_once(lambda dt: self._retomar(ws), mins_pausa * 60)
                return
        else:
            self.losses_f1  += 1
            self.stake_atual = round(self.stake_atual * gale_mult, 2)
            if self.losses_f1 >= losses_max:
                self.log(f"⚡ FASE 2 ativada após {losses_max} losses", "warn")
                self.losses_f1   = 0
                self.stake_atual = stake_base

        Clock.schedule_once(lambda dt: self._comprar(ws), 0.5)

    def _retomar(self, ws):
        self.log("▶ Retomando após pausa", "info")
        self.em_pausa = False
        self._comprar(ws)

# ═══════════════════════ TELA DE LICENÇA ════════════════════════════
class LicencaScreen(Screen):
    def __init__(self, on_ok, **kw):
        super().__init__(**kw)
        self.on_ok = on_ok
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16))
        with root.canvas.before:
            Color(*C_BG)
            self._bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=lambda i, v: setattr(self._bg, "size", v),
                  pos=lambda i, v: setattr(self._bg, "pos", v))

        root.add_widget(Widget())
        root.add_widget(lbl("FIDESx v9", color=C_GOLD, size=sp(28), bold=True, halign="center"))
        root.add_widget(lbl("Deriv Auto Trading", color=C_GRAY, size=sp(13), halign="center"))
        root.add_widget(Widget(size_hint_y=None, height=dp(20)))
        root.add_widget(lbl("Código de licença:", color=C_WHITE, size=sp(13)))

        self.inp = dark_input(hint="XXXX-XXXXXX-YYYY", height=dp(48))
        self.inp.height = dp(48)
        self.inp.size_hint_y = None
        root.add_widget(self.inp)

        self.lbl_err = lbl("", color=C_RED, size=sp(12), halign="center")
        root.add_widget(self.lbl_err)

        btn = dark_btn("ATIVAR  →", color=C_GOLD, height=dp(52))
        btn.bind(on_release=self._ativar)
        root.add_widget(btn)

        root.add_widget(Widget())
        self.add_widget(root)

    def _ativar(self, *a):
        codigo = self.inp.text.strip()
        plano, erro = validar_licenca(codigo)
        if erro:
            self.lbl_err.text = f"❌ {erro}"
            return
        _lic_salvar(codigo)
        self.on_ok(plano, codigo)

# ═══════════════════════ TELA PRINCIPAL ═════════════════════════════
class MainScreen(Screen):
    def __init__(self, cfg, plano, **kw):
        super().__init__(**kw)
        self.cfg   = dict(DEFAULT)
        self.cfg.update(cfg)
        self.plano = plano
        self.bot   = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*C_BG)
            self._bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=lambda i, v: setattr(self._bg, "size", v),
                  pos=lambda i, v: setattr(self._bg, "pos", v))

        # Header
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(56),
            padding=[dp(16), dp(8)],
        )
        with header.canvas.before:
            Color(*C_PANEL)
            self._hbg = Rectangle(size=header.size, pos=header.pos)
        header.bind(size=lambda i, v: setattr(self._hbg, "size", v),
                    pos=lambda i, v: setattr(self._hbg, "pos", v))

        cor_plano = {"STANDARD": C_GOLD, "PREMIUM": C_CYAN, "ADMIN": C_GREEN}.get(self.plano, C_GOLD)
        ico_plano = {"STANDARD": "⭐", "PREMIUM": "💎", "ADMIN": "👑"}.get(self.plano, "⭐")

        header.add_widget(Label(text=f"FIDESx v9", color=C_GOLD, font_size=sp(16),
                                bold=True, halign="left", size_hint_x=0.5))
        header.add_widget(Label(text=f"{ico_plano} {self.plano}", color=cor_plano,
                                font_size=sp(12), halign="right", size_hint_x=0.3))
        self.lbl_saldo = Label(text="$0.00", color=C_GREEN, font_size=sp(14),
                               bold=True, halign="right", size_hint_x=0.2)
        header.add_widget(self.lbl_saldo)
        root.add_widget(header)

        # Tabs simuladas
        tabs = BoxLayout(size_hint_y=None, height=dp(42))
        with tabs.canvas.before:
            Color(*C_PANEL)
            self._tbg = Rectangle(size=tabs.size, pos=tabs.pos)
        tabs.bind(size=lambda i, v: setattr(self._tbg, "size", v),
                  pos=lambda i, v: setattr(self._tbg, "pos", v))

        self._tab_btns = {}
        for nome in ["CONFIG", "TRADING", "LOG"]:
            b = Button(
                text=nome, font_size=sp(12), bold=True,
                background_normal="", background_color=C_PANEL,
                color=C_GRAY,
            )
            b.bind(on_release=partial(self._mudar_tab, nome))
            tabs.add_widget(b)
            self._tab_btns[nome] = b
        root.add_widget(tabs)

        # Conteúdo
        self._pages = {}

        self._pages["CONFIG"]  = self._build_config()
        self._pages["TRADING"] = self._build_trading()
        self._pages["LOG"]     = self._build_log()

        self._content = BoxLayout()
        for p in self._pages.values():
            self._content.add_widget(p)
        root.add_widget(self._content)

        self.add_widget(root)
        self._mudar_tab("CONFIG")

    def _mudar_tab(self, nome, *a):
        for k, p in self._pages.items():
            p.opacity  = 1 if k == nome else 0
            p.disabled = k != nome
        for k, b in self._tab_btns.items():
            b.color            = C_GOLD if k == nome else C_GRAY
            b.background_color = C_CARD  if k == nome else C_PANEL

    def _scroll_box(self):
        sv  = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(16), spacing=dp(10))
        box.bind(minimum_height=box.setter("height"))
        sv.add_widget(box)
        return sv, box

    def _field(self, box, label_txt, widget):
        box.add_widget(lbl(label_txt, color=C_GRAY, size=sp(11)))
        box.add_widget(widget)

    def _build_config(self):
        sv, box = self._scroll_box()

        box.add_widget(lbl("⚙ CONFIGURAÇÕES", color=C_GOLD, size=sp(14), bold=True))
        box.add_widget(separator())

        # Token API
        box.add_widget(lbl("Token API Deriv:", color=C_GRAY, size=sp(11)))
        self.inp_token = dark_input(hint="Token da sua conta Deriv", text=self.cfg.get("api_token", ""))
        box.add_widget(self.inp_token)

        # Mercado
        box.add_widget(lbl("Mercado:", color=C_GRAY, size=sp(11)))
        self.spin_mercado = Spinner(
            text=self.cfg.get("mercado", "1HZ10V"),
            values=MERCADOS,
            size_hint_y=None, height=dp(42),
            background_normal="", background_color=C_INPUT,
            color=C_WHITE, font_size=sp(13),
        )
        box.add_widget(self.spin_mercado)

        # Contrato
        box.add_widget(lbl("Contrato:", color=C_GRAY, size=sp(11)))
        self.spin_contrato = Spinner(
            text=self.cfg.get("contrato", "DIGITOVER"),
            values=TIPOS_CONTRATO,
            size_hint_y=None, height=dp(42),
            background_normal="", background_color=C_INPUT,
            color=C_WHITE, font_size=sp(13),
        )
        box.add_widget(self.spin_contrato)

        # Grid de campos numéricos
        campos = [
            ("Barreira:", "barreira", "3"),
            ("Duração (t):", "duracao", "1"),
            ("Stake $:", "stake", "1.00"),
            ("Gale Mult.:", "gale_mult", "2.0"),
            ("Profit Alvo $:", "profit_alvo", "10.00"),
            ("Stop Loss $:", "stop_loss", "100.00"),
            ("Losses F1:", "losses_fase1", "3"),
            ("Wins Pausa:", "wins_pausa", "3"),
            ("Min Pausa:", "minutos_pausa", "5"),
        ]
        self._inps = {}
        grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(8))
        grid.bind(minimum_height=grid.setter("height"))

        for label_txt, key, default in campos:
            col = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(70), spacing=dp(4))
            col.add_widget(lbl(label_txt, color=C_GRAY, size=sp(11)))
            inp = dark_input(text=self.cfg.get(key, default))
            inp.height = dp(42)
            col.add_widget(inp)
            self._inps[key] = inp
            grid.add_widget(col)

        box.add_widget(grid)
        box.add_widget(separator())

        btn = dark_btn("💾  SALVAR CONFIGURAÇÕES", color=C_CYAN, height=dp(50))
        btn.bind(on_release=self._salvar_cfg)
        box.add_widget(btn)

        return sv

    def _build_trading(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        with root.canvas.before:
            Color(*C_BG)
            _bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=lambda i, v: setattr(_bg, "size", v),
                  pos=lambda i, v: setattr(_bg, "pos", v))

        # Painel de status
        status_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(140),
                               padding=dp(16), spacing=dp(8))
        with status_box.canvas.before:
            Color(*C_CARD)
            _sbg = RoundedRectangle(radius=[dp(10)], size=status_box.size, pos=status_box.pos)
        status_box.bind(size=lambda i, v: setattr(_sbg, "size", v),
                        pos=lambda i, v: setattr(_sbg, "pos", v))

        self.lbl_status = Label(text="● PARADO", color=C_GRAY, font_size=sp(15),
                                bold=True, halign="center")
        self.lbl_lucro  = Label(text="P&L: $0.00", color=C_WHITE, font_size=sp(22),
                                bold=True, halign="center")
        self.lbl_info   = Label(text="Configure e inicie o bot", color=C_GRAY,
                                font_size=sp(11), halign="center")

        status_box.add_widget(self.lbl_status)
        status_box.add_widget(self.lbl_lucro)
        status_box.add_widget(self.lbl_info)
        root.add_widget(status_box)

        # Botões
        self.btn_start = dark_btn("▶  INICIAR BOT", color=C_GREEN, height=dp(58))
        self.btn_start.bind(on_release=self._iniciar)
        root.add_widget(self.btn_start)

        self.btn_stop = dark_btn("■  PARAR BOT", color=C_RED, height=dp(50))
        self.btn_stop.bind(on_release=self._parar)
        self.btn_stop.disabled = True
        root.add_widget(self.btn_stop)

        root.add_widget(Widget())
        return root

    def _build_log(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))
        with root.canvas.before:
            Color(*C_BG)
            _bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=lambda i, v: setattr(_bg, "size", v),
                  pos=lambda i, v: setattr(_bg, "pos", v))

        topo = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        topo.add_widget(lbl("📋 LOG DO BOT", color=C_GOLD, size=sp(13), bold=True))
        btn_limpar = dark_btn("🗑 Limpar", color=C_GRAY, height=dp(34))
        btn_limpar.size_hint_x = None
        btn_limpar.width = dp(90)
        btn_limpar.bind(on_release=lambda *a: setattr(self.log_txt, "text", ""))
        topo.add_widget(btn_limpar)
        root.add_widget(topo)

        sv = ScrollView()
        self.log_txt = TextInput(
            text="", readonly=True, multiline=True,
            background_color=C_CARD,
            foreground_color=C_WHITE,
            font_size=sp(11),
            background_normal="",
            background_active="",
        )
        sv.add_widget(self.log_txt)
        root.add_widget(sv)
        return root

    def _salvar_cfg(self, *a):
        self.cfg["api_token"] = self.inp_token.text.strip()
        self.cfg["mercado"]   = self.spin_mercado.text
        self.cfg["contrato"]  = self.spin_contrato.text
        for key, inp in self._inps.items():
            self.cfg[key] = inp.text.strip()
        _cfg_salvar(self.cfg)
        self._popup("✅ Configurações salvas!", color=C_GREEN)

    def _iniciar(self, *a):
        self._salvar_cfg()
        if not self.cfg.get("api_token", "").strip():
            self._popup("❌ Configure o Token API primeiro!", color=C_RED)
            return
        self.bot = FIDESxBot(
            cfg=self.cfg,
            log_cb=self._on_log,
            balance_cb=self._on_balance,
            stop_cb=self._on_stop,
        )
        self.bot.iniciar()
        self.btn_start.disabled = True
        self.btn_stop.disabled  = False
        self.lbl_status.text    = "● RODANDO"
        self.lbl_status.color   = C_GREEN
        self._mudar_tab("TRADING")

    def _parar(self, *a):
        if self.bot:
            self.bot.parar()
        self._on_stop()

    def _on_stop(self):
        self.btn_start.disabled = False
        self.btn_stop.disabled  = True
        self.lbl_status.text    = "● PARADO"
        self.lbl_status.color   = C_GRAY

    def _on_balance(self, saldo):
        self.lbl_saldo.text = f"${saldo:.2f}"

    def _on_log(self, linha, tag):
        cores = {"ok": "[color=00e676]", "error": "[color=ff3d5a]",
                 "warn": "[color=e8b84b]", "trade": "[color=00ffe0]",
                 "info": "[color=dce8f5]"}
        c = cores.get(tag, cores["info"])
        self.log_txt.text += f"{c}{linha}[/color]\n"

        if self.bot:
            lp = self.bot.lucro_total
            cor = C_GREEN if lp >= 0 else C_RED
            self.lbl_lucro.text  = f"P&L: ${lp:+.2f}"
            self.lbl_lucro.color = cor

    def _popup(self, msg, color=None):
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        box.add_widget(Label(text=msg, color=color or C_WHITE, font_size=sp(13)))
        btn = dark_btn("OK", color=color or C_GOLD)
        pop = Popup(title="FIDESx", content=box,
                    size_hint=(0.85, None), height=dp(180),
                    background_color=C_CARD,
                    separator_color=C_BORDER)
        btn.bind(on_release=pop.dismiss)
        box.add_widget(btn)
        pop.open()

# ═══════════════════════ APP ════════════════════════════════════════
class FIDESxApp(App):
    def build(self):
        Window.clearcolor = (*C_BG[:3], 1)
        self.title = "FIDESx v9"
        self.sm    = ScreenManager(transition=SlideTransition())

        codigo = _lic_carregar()
        if codigo:
            plano, erro = validar_licenca(codigo)
            if not erro:
                self._abrir_main(plano, codigo)
                return self.sm

        ls = LicencaScreen(name="licenca", on_ok=self._abrir_main)
        self.sm.add_widget(ls)
        return self.sm

    def _abrir_main(self, plano, codigo):
        cfg = _cfg_carregar()
        ms  = MainScreen(name="main", cfg=cfg, plano=plano)
        if "main" not in [s.name for s in self.sm.screens]:
            self.sm.add_widget(ms)
        self.sm.current = "main"

if __name__ == "__main__":
    FIDESxApp().run()
