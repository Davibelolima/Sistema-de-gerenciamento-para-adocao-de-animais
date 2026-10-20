
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import hashlib
import hmac
import secrets
import getpass
import sys
import shutil
import uuid
from pathlib import Path
from PIL import Image, ImageOps, ImageTk

# Mantém usuários e animais no mesmo banco mesmo se o app iniciar de outra pasta.
PASTA_PROJETO = Path.home() / "OneDrive" / "Desktop" / "projeto controle de animais p adoção"
if PASTA_PROJETO.is_dir():
    DB = str(PASTA_PROJETO / "viralar.db")
else:
    DB = str(Path(__file__).resolve().with_name("viralar.db"))

# Cores compartilhadas por todas as telas.
CORES = {
    "fundo": "#F5F7F4",
    "painel": "#FFFFFF",
    "verde": "#2F6B4F",
    "verde_claro": "#E5F0E9",
    "laranja": "#D9822B",
    "texto": "#243029",
    "cinza": "#6B756E",
    "borda": "#DDE4DF",
    "vermelho": "#B94A48"
}


def validar_entrada(valor, tipo):
    if not valor:
        return True
    if tipo == "numero":
        return valor.isdecimal()
    if tipo == "texto":
        return all(
            caractere.isalpha()
            or caractere.isspace()
            or caractere in "-'."
            for caractere in valor
        )
    return True


class ViraLar:
    # Ponto de entrada: prepara o banco, cria a interface e carrega a tela inicial.
    def __init__(self, root):
        self.root = root
        self.root.title("ViraLar | Gestão de adoções")
        self.root.geometry("1150x720")
        self.root.minsize(950, 600)
        self.root.configure(bg=CORES["fundo"])

        # A conexão permanece aberta até a janela ser fechada.
        self.db = sqlite3.connect(DB)
        self.criar_banco()
        self.criar_banco_usuarios()
        self.criar_dados_iniciais()

        # A tela atual é reconstruída sempre que este valor muda.
        self.view = "inicio"
        self.animais = []
        self.usuario_logado = None

        self.root.protocol("WM_DELETE_WINDOW", self.fechar)
        self.mostrar_acesso()

    # Cria a tabela principal caso ela ainda não exista.
    def criar_banco(self):
        # IF NOT EXISTS preserva os dados já cadastrados entre execuções.
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS animais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                especie TEXT NOT NULL,
                idade TEXT NOT NULL,
                sexo TEXT NOT NULL,
                porte TEXT NOT NULL,
                status TEXT NOT NULL,
                observacoes TEXT,
                imagem TEXT NOT NULL DEFAULT ''
            )
        """)
        self.db.commit()
        colunas = {
            coluna[1] for coluna in self.db.execute("PRAGMA table_info(animais)")
        }
        if "imagem" not in colunas:
            self.db.execute(
                "ALTER TABLE animais ADD COLUMN imagem TEXT NOT NULL DEFAULT ''"
            )
            self.db.commit()

    def criar_banco_usuarios(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                usuario TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL DEFAULT '',
                telefone TEXT NOT NULL DEFAULT '',
                senha_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                perfil TEXT NOT NULL CHECK (perfil IN ('admin', 'usuario')),
                ativo INTEGER NOT NULL DEFAULT 1,
                pode_editar INTEGER NOT NULL DEFAULT 0,
                pode_mudar_status INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.db.commit()
        colunas_usuario = {
            coluna[1] for coluna in self.db.execute("PRAGMA table_info(usuarios)")
        }
        for coluna, definicao in (
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("telefone", "TEXT NOT NULL DEFAULT ''"),
            ("pode_editar", "INTEGER NOT NULL DEFAULT 0"),
            ("pode_mudar_status", "INTEGER NOT NULL DEFAULT 0")
        ):
            if coluna not in colunas_usuario:
                self.db.execute(
                    f"ALTER TABLE usuarios ADD COLUMN {coluna} {definicao}"
                )
        self.db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS usuarios_email_unico
            ON usuarios(email COLLATE NOCASE) WHERE email != ''
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                telefone TEXT NOT NULL,
                interesse TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.commit()

    @staticmethod
    def gerar_hash_senha(senha, salt):
        return hashlib.pbkdf2_hmac(
            "sha256",
            senha.encode("utf-8"),
            bytes.fromhex(salt),
            310000
        ).hex()

    def criar_usuario(
        self,
        nome,
        usuario,
        senha,
        email="",
        telefone=""
    ):
        salt = secrets.token_hex(16)
        senha_hash = self.gerar_hash_senha(senha, salt)
        cursor = self.db.execute("""
            INSERT INTO usuarios
            (nome, usuario, email, telefone, senha_hash, salt, perfil)
            VALUES (?, ?, ?, ?, ?, ?, 'usuario')
        """, (nome, usuario, email, telefone, senha_hash, salt))
        self.db.commit()
        return cursor.lastrowid

    def eh_admin(self):
        if not self.usuario_logado:
            return False
        conta = self.db.execute(
            "SELECT perfil, ativo FROM usuarios WHERE id = ?",
            (self.usuario_logado[0],)
        ).fetchone()
        return bool(conta and conta[0] == "admin" and conta[1])

    def tem_permissao(self, permissao):
        if not self.usuario_logado:
            return False
        if self.eh_admin():
            return True
        coluna = {
            "editar": "pode_editar",
            "status": "pode_mudar_status"
        }.get(permissao)
        if not coluna:
            return False
        conta = self.db.execute(
            f"SELECT {coluna}, ativo FROM usuarios WHERE id = ?",
            (self.usuario_logado[0],)
        ).fetchone()
        return bool(conta and conta[1] and conta[0])

    def mostrar_acesso(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.usuario_logado = None
        self.root.geometry("640x620")
        self.root.minsize(520, 500)
        self.tela_acesso = tk.Frame(self.root, bg=CORES["fundo"])
        self.tela_acesso.pack(fill="both", expand=True)

        painel = tk.Frame(
            self.tela_acesso,
            bg=CORES["painel"],
            highlightbackground=CORES["borda"],
            highlightthickness=1,
            padx=35,
            pady=30
        )
        painel.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            painel,
            text="ViraLar",
            font=("Arial", 27, "bold"),
            fg=CORES["verde"],
            bg=CORES["painel"]
        ).pack(anchor="w")
        tk.Label(
            painel,
            text="Acessar o projeto",
            font=("Arial", 17, "bold"),
            fg=CORES["texto"],
            bg=CORES["painel"]
        ).pack(anchor="w", pady=(18, 4))
        tk.Label(
            painel,
            text="Entre com sua conta ou crie um cadastro.",
            font=("Arial", 10),
            fg=CORES["cinza"],
            bg=CORES["painel"]
        ).pack(anchor="w", pady=(0, 18))

        self.acesso_usuario = tk.StringVar()
        self.acesso_senha = tk.StringVar()
        self.campo_acesso(painel, "Usuário", self.acesso_usuario)
        self.campo_acesso(painel, "Senha", self.acesso_senha, senha=True)

        tk.Button(
            painel,
            text="Entrar",
            command=self.processar_acesso,
            font=("Arial", 10, "bold"),
            bg=CORES["verde"],
            fg="white",
            activebackground="#3D7D5D",
            activeforeground="white",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2"
        ).pack(fill="x", pady=(12, 0))
        tk.Button(
            painel,
            text="Criar conta",
            command=self.formulario_cadastro_usuario,
            font=("Arial", 9),
            bg=CORES["painel"],
            fg=CORES["verde"],
            activebackground=CORES["verde_claro"],
            bd=0,
            pady=9,
            cursor="hand2"
        ).pack(fill="x", pady=(5, 0))

    def campo_acesso(self, pai, rotulo, variavel, senha=False):
        tk.Label(
            pai,
            text=rotulo,
            font=("Arial", 10, "bold"),
            fg=CORES["texto"],
            bg=CORES["painel"]
        ).pack(anchor="w", pady=(7, 4))
        tk.Entry(
            pai,
            textvariable=variavel,
            show="*" if senha else "",
            font=("Arial", 11),
            relief="solid",
            bd=1,
            width=35
        ).pack(fill="x", ipady=7)

    def processar_acesso(self):
        usuario = self.acesso_usuario.get().strip()
        senha = self.acesso_senha.get()

        conta = self.db.execute("""
            SELECT id, nome, usuario, senha_hash, salt, perfil,
                   pode_editar, pode_mudar_status
            FROM usuarios
            WHERE usuario = ? COLLATE NOCASE AND ativo = 1
        """, (usuario,)).fetchone()

        if conta and hmac.compare_digest(
            conta[3], self.gerar_hash_senha(senha, conta[4])
        ):
            self.usuario_logado = (
                conta[0], conta[1], conta[2], conta[5], conta[6], conta[7]
            )
            self.iniciar_sessao()
            return

        messagebox.showerror("ViraLar", "Usuário ou senha inválidos.")

    def formulario_cadastro_usuario(self):
        janela = tk.Toplevel(self.root)
        janela.title("Criar conta")
        janela.geometry("480x700")
        janela.resizable(False, False)
        janela.configure(bg=CORES["fundo"])
        janela.transient(self.root)
        janela.grab_set()

        formulario = tk.Frame(janela, bg=CORES["fundo"], padx=30, pady=24)
        formulario.pack(fill="both", expand=True)
        tk.Label(
            formulario,
            text="Criar conta de usuário",
            font=("Arial", 21, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w")
        tk.Label(
            formulario,
            text="Novas contas começam sem permissão para alterar dados.",
            font=("Arial", 10),
            fg=CORES["cinza"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(5, 14))

        nome = tk.StringVar()
        email = tk.StringVar()
        telefone = tk.StringVar()
        usuario = tk.StringVar()
        senha = tk.StringVar()
        confirmacao = tk.StringVar()

        def campo(rotulo, variavel, senha_oculta=False):
            tk.Label(
                formulario,
                text=rotulo,
                font=("Arial", 10, "bold"),
                fg=CORES["texto"],
                bg=CORES["fundo"]
            ).pack(anchor="w", pady=(8, 4))
            tk.Entry(
                formulario,
                textvariable=variavel,
                show="*" if senha_oculta else "",
                font=("Arial", 10),
                relief="solid",
                bd=1
            ).pack(fill="x", ipady=7)

        campo("Nome completo", nome)
        campo("E-mail", email)
        campo("Telefone / WhatsApp", telefone)
        campo("Usuário (sem espaços)", usuario)
        campo("Senha (mínimo 8 caracteres)", senha, senha_oculta=True)
        campo("Confirmar senha", confirmacao, senha_oculta=True)

        botoes = tk.Frame(formulario, bg=CORES["fundo"])
        botoes.pack(fill="x", pady=(22, 0))
        tk.Button(
            botoes,
            text="Cancelar",
            command=janela.destroy,
            bg="#E1E6E2",
            fg=CORES["texto"],
            bd=0,
            padx=16,
            pady=9
        ).pack(side="right", padx=(8, 0))

        def salvar_usuario():
            nome_final = nome.get().strip()
            email_final = email.get().strip().lower()
            telefone_final = telefone.get().strip()
            usuario_final = usuario.get().strip()
            senha_final = senha.get()
            digitos_telefone = "".join(
                caractere for caractere in telefone_final
                if caractere.isdecimal()
            )
            if not nome_final:
                messagebox.showwarning("ViraLar", "Informe seu nome.")
                return
            if email_final.count("@") != 1 or "." not in email_final.rsplit("@", 1)[-1]:
                messagebox.showwarning("ViraLar", "Informe um e-mail válido.")
                return
            if len(digitos_telefone) < 10:
                messagebox.showwarning("ViraLar", "Informe um telefone com DDD.")
                return
            if len(usuario_final) < 3 or not all(
                caractere.isalnum() or caractere in "._-"
                for caractere in usuario_final
            ):
                messagebox.showwarning(
                    "ViraLar",
                    "O usuário deve ter 3 ou mais caracteres, sem espaços."
                )
                return
            if len(senha_final) < 8:
                messagebox.showwarning(
                    "ViraLar",
                    "A senha precisa ter pelo menos 8 caracteres."
                )
                return
            if senha_final != confirmacao.get():
                messagebox.showwarning("ViraLar", "As senhas não coincidem.")
                return
            try:
                self.criar_usuario(
                    nome_final,
                    usuario_final,
                    senha_final,
                    email=email_final,
                    telefone=telefone_final
                )
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "ViraLar",
                    "Este usuário ou e-mail já está cadastrado."
                )
                return
            self.acesso_usuario.set(usuario_final)
            self.acesso_senha.set("")
            janela.destroy()
            messagebox.showinfo(
                "Conta criada",
                "Sua conta foi criada. Entre para acessar o projeto em modo de leitura."
            )

        tk.Button(
            botoes,
            text="Criar conta",
            command=salvar_usuario,
            bg=CORES["verde"],
            fg="white",
            bd=0,
            padx=16,
            pady=9,
            cursor="hand2"
        ).pack(side="right")

    def iniciar_sessao(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.geometry("1150x720")
        self.root.minsize(950, 600)
        self.view = "inicio"
        self.criar_interface()
        self.atualizar_tela()

    def sair(self):
        self.mostrar_acesso()

    # Adiciona registros de exemplo apenas no primeiro uso.
    def criar_dados_iniciais(self):
        # A contagem evita inserir os mesmos exemplos toda vez que o programa abre.
        quantidade = self.db.execute(
            "SELECT COUNT(*) FROM animais"
        ).fetchone()[0]

        if quantidade == 0:
            dados = [
                ("Luna", "Cachorro", "2 anos", "Fêmea", "Médio", "Disponível", "Carinhosa e brincalhona."),
                ("Tobias", "Cachorro", "4 anos", "Macho", "Grande", "Em análise", "Calmo e dócil."),
                ("Amora", "Gato", "1 ano", "Fêmea", "Pequeno", "Disponível", "Muito tranquila."),
                ("Bento", "Cachorro", "3 anos", "Macho", "Médio", "Adotado", "Adora brincar."),
                ("Pipoca", "Gato", "2 anos", "Fêmea", "Pequeno", "Disponível", "Curiosa e carinhosa."),
                ("Nina", "Cachorro", "5 anos", "Fêmea", "Médio", "Em análise", "Muito companheira.")
            ]

            self.db.executemany("""
                INSERT INTO animais
                (nome, especie, idade, sexo, porte, status, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, dados)
            self.db.commit()

    # Monta o menu lateral e a área de conteúdo.
    def criar_interface(self):
        # O menu fica fixo à esquerda; o conteúdo ocupa o espaço restante.
        self.menu = tk.Frame(
            self.root,
            bg=CORES["verde"],
            width=220
        )
        self.menu.pack(side="left", fill="y")
        self.menu.pack_propagate(False)

        logo = tk.Label(
            self.menu,
            text="ViraLar",
            font=("Arial", 25, "bold"),
            fg="white",
            bg=CORES["verde"]
        )
        logo.pack(pady=(35, 5))

        subtitulo = tk.Label(
            self.menu,
            text="Gestão de adoções",
            font=("Arial", 10),
            fg="#DCEBE2",
            bg=CORES["verde"]
        )
        subtitulo.pack(pady=(0, 35))

        self.botao_inicio = self.criar_menu(
            "Visão geral",
            lambda: self.mudar_view("inicio")
        )

        self.botao_adocoes = self.criar_menu(
            "Adoções",
            lambda: self.mudar_view("adocoes")
        )

        if self.eh_admin():
            self.criar_menu(
                "Usuários",
                lambda: self.mudar_view("usuarios")
            )

        if self.tem_permissao("editar"):
            self.criar_menu("Novo animal", self.novo_animal)

        tk.Frame(
            self.menu,
            bg=CORES["verde"]
        ).pack(expand=True, fill="both")

        perfil = "Administrador" if self.usuario_logado[3] == "admin" else "Usuário"
        rodape = tk.Label(
            self.menu,
            text=f"{self.usuario_logado[1]}\n{perfil}",
            font=("Arial", 9),
            fg="#DCEBE2",
            bg=CORES["verde"],
            justify="left",
            wraplength=175
        )
        rodape.pack(pady=(15, 8), padx=20, anchor="w")

        tk.Button(
            self.menu,
            text="Sair da conta",
            command=self.sair,
            font=("Arial", 9),
            anchor="w",
            padx=20,
            pady=7,
            bd=0,
            fg="white",
            bg="#28573F",
            activebackground="#3D7D5D",
            activeforeground="white",
            cursor="hand2"
        ).pack(fill="x", padx=10)

        self.conteudo = tk.Frame(
            self.root,
            bg=CORES["fundo"]
        )
        self.conteudo.pack(
            side="right",
            expand=True,
            fill="both"
        )

    # Cria um botão padronizado para o menu lateral.
    def criar_menu(self, texto, comando):
        botao = tk.Button(
            self.menu,
            text=texto,
            command=comando,
            font=("Arial", 11),
            anchor="w",
            padx=25,
            bd=0,
            relief="flat",
            fg="white",
            bg=CORES["verde"],
            activebackground="#3D7D5D",
            activeforeground="white",
            cursor="hand2"
        )
        botao.pack(fill="x", pady=2)
        return botao

    # Remove os widgets da tela antes de carregar outra view.
    def limpar_conteudo(self):
        # As telas são recriadas para refletir imediatamente as alterações no banco.
        for widget in self.conteudo.winfo_children():
            widget.destroy()

    def mudar_view(self, view):
        # Guarda a tela escolhida e solicita sua reconstrução.
        if view == "usuarios" and not self.eh_admin():
            messagebox.showerror("ViraLar", "Apenas o administrador pode autorizar usuários.")
            return
        self.view = view
        self.atualizar_tela()

    def atualizar_tela(self):
        # Impede que widgets de telas diferentes fiquem sobrepostos.
        self.limpar_conteudo()

        if self.view == "inicio":
            self.mostrar_inicio()
        elif self.view == "adocoes":
            self.mostrar_adocoes()
        elif self.view == "usuarios" and self.eh_admin():
            self.mostrar_usuarios()

    def mostrar_usuarios(self):
        self.titulo(
            "Permissões de usuários",
            "Contas novas começam em modo de leitura. Autorize cada ação necessária."
        )
        area = tk.Frame(
            self.conteudo,
            bg=CORES["painel"],
            highlightbackground=CORES["borda"],
            highlightthickness=1
        )
        area.pack(fill="both", expand=True, padx=35, pady=(0, 30))
        topo = tk.Frame(area, bg=CORES["painel"])
        topo.pack(fill="x", padx=20, pady=18)
        tk.Label(
            topo,
            text="Contas cadastradas",
            font=("Arial", 15, "bold"),
            fg=CORES["texto"],
            bg=CORES["painel"]
        ).pack(side="left")
        tabela_frame = tk.Frame(area, bg=CORES["painel"])
        tabela_frame.pack(fill="both", expand=True, padx=20)
        tree = ttk.Treeview(
            tabela_frame,
            columns=("nome", "usuario", "email", "editar", "status"),
            show="headings",
            height=12
        )
        for coluna, rotulo, largura in (
            ("nome", "Nome", 170),
            ("usuario", "Usuário", 140),
            ("email", "E-mail", 220),
            ("editar", "Cadastro/edição", 140),
            ("status", "Status adoção", 130)
        ):
            tree.heading(coluna, text=rotulo)
            tree.column(coluna, width=largura, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(
            tabela_frame,
            orient="vertical",
            command=tree.yview
        )
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.preencher_usuarios(tree)

        botoes = tk.Frame(area, bg=CORES["painel"])
        botoes.pack(fill="x", padx=20, pady=18)
        tk.Button(
            botoes,
            text="Autorizar / revogar cadastro e edição",
            command=lambda: self.alternar_permissao_usuario(tree, "pode_editar"),
            bg="#E8EEE9",
            fg=CORES["texto"],
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            botoes,
            text="Autorizar / revogar mudança de status",
            command=lambda: self.alternar_permissao_usuario(tree, "pode_mudar_status"),
            bg=CORES["verde"],
            fg="white",
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2"
        ).pack(side="left", padx=8)

    def preencher_usuarios(self, tree):
        for item in tree.get_children():
            tree.delete(item)
        usuarios = self.db.execute("""
            SELECT id, nome, usuario, email, pode_editar, pode_mudar_status
            FROM usuarios WHERE perfil = 'usuario'
            ORDER BY nome COLLATE NOCASE
        """).fetchall()
        for usuario in usuarios:
            tree.insert(
                "",
                "end",
                iid=str(usuario[0]),
                values=(
                    usuario[1],
                    usuario[2],
                    usuario[3],
                    "Permitido" if usuario[4] else "Bloqueado",
                    "Permitido" if usuario[5] else "Bloqueado"
                )
            )

    def alternar_permissao_usuario(self, tree, permissao):
        if not self.eh_admin():
            messagebox.showerror("ViraLar", "Apenas o administrador pode alterar permissões.")
            return
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showinfo("ViraLar", "Selecione um usuário primeiro.")
            return
        if permissao not in {"pode_editar", "pode_mudar_status"}:
            return
        usuario_id = int(selecionado[0])
        atual = self.db.execute(
            f"SELECT {permissao} FROM usuarios WHERE id = ? AND perfil = 'usuario'",
            (usuario_id,)
        ).fetchone()
        if atual is None:
            messagebox.showerror("ViraLar", "Usuário não encontrado.")
            return
        self.db.execute(
            f"UPDATE usuarios SET {permissao} = ? WHERE id = ?",
            (0 if atual[0] else 1, usuario_id)
        )
        self.db.commit()
        self.preencher_usuarios(tree)

    def novo_usuario(self):
        self.formulario_usuario()

    def editar_usuario(self, tree):
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showinfo("ViraLar", "Selecione um usuário para editar.")
            return
        self.formulario_usuario(int(selecionado[0]))

    def formulario_usuario(self, usuario_id=None):
        return
        conta = None
        if usuario_id is not None:
            conta = self.db.execute("""
                SELECT id, nome, usuario, perfil, ativo
                FROM usuarios WHERE id = ?
            """, (usuario_id,)).fetchone()
            if conta is None:
                messagebox.showerror("ViraLar", "Usuário não encontrado.")
                return

        janela = tk.Toplevel(self.root)
        janela.title("Novo usuário" if conta is None else "Editar usuário")
        janela.geometry("480x590")
        janela.resizable(False, False)
        janela.configure(bg=CORES["fundo"])
        janela.transient(self.root)
        janela.grab_set()
        formulario = tk.Frame(janela, bg=CORES["fundo"], padx=30, pady=25)
        formulario.pack(fill="both", expand=True)

        tk.Label(
            formulario,
            text="Novo usuário" if conta is None else "Editar usuário",
            font=("Arial", 20, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(0, 18))

        nome = tk.StringVar(value=conta[1] if conta else "")
        usuario = tk.StringVar(value=conta[2] if conta else "")
        perfil = tk.StringVar(
            value="Administrador" if conta and conta[3] == "admin" else "Usuário"
        )
        senha = tk.StringVar()
        confirmacao = tk.StringVar()

        def adicionar_campo(rotulo, variavel, senha_oculta=False):
            tk.Label(
                formulario,
                text=rotulo,
                font=("Arial", 10, "bold"),
                fg=CORES["texto"],
                bg=CORES["fundo"]
            ).pack(anchor="w", pady=(8, 4))
            tk.Entry(
                formulario,
                textvariable=variavel,
                show="*" if senha_oculta else "",
                font=("Arial", 10),
                relief="solid",
                bd=1
            ).pack(fill="x", ipady=6)

        adicionar_campo("Nome", nome)
        adicionar_campo("Usuário (sem espaços)", usuario)
        tk.Label(
            formulario,
            text="Perfil",
            font=("Arial", 10, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(8, 4))
        ttk.Combobox(
            formulario,
            textvariable=perfil,
            values=("Administrador", "Usuário"),
            state="readonly"
        ).pack(fill="x", ipady=5)
        adicionar_campo(
            "Nova senha (mínimo 8 caracteres)" if conta else "Senha (mínimo 8 caracteres)",
            senha,
            senha_oculta=True
        )
        adicionar_campo("Confirmar senha", confirmacao, senha_oculta=True)
        if conta:
            tk.Label(
                formulario,
                text="Deixe a senha em branco para mantê-la.",
                font=("Arial", 9),
                fg=CORES["cinza"],
                bg=CORES["fundo"]
            ).pack(anchor="w", pady=(5, 0))

        botoes = tk.Frame(formulario, bg=CORES["fundo"])
        botoes.pack(fill="x", pady=(20, 0))
        tk.Button(
            botoes,
            text="Cancelar",
            command=janela.destroy,
            bg="#E1E6E2",
            fg=CORES["texto"],
            bd=0,
            padx=18,
            pady=9
        ).pack(side="right", padx=(8, 0))

        def salvar_usuario():
            nome_final = nome.get().strip()
            usuario_final = usuario.get().strip()
            senha_final = senha.get()
            perfil_final = "admin" if perfil.get() == "Administrador" else "usuario"

            if not nome_final or not usuario_final:
                messagebox.showwarning("ViraLar", "Preencha o nome e o usuário.")
                return
            if len(usuario_final) < 3 or not all(
                caractere.isalnum() or caractere in "._-"
                for caractere in usuario_final
            ):
                messagebox.showwarning(
                    "ViraLar",
                    "O usuário deve ter 3 ou mais caracteres, sem espaços."
                )
                return
            if (conta is None or senha_final) and len(senha_final) < 8:
                messagebox.showwarning(
                    "ViraLar",
                    "A senha precisa ter pelo menos 8 caracteres."
                )
                return
            if senha_final != confirmacao.get():
                messagebox.showwarning("ViraLar", "As senhas não coincidem.")
                return
            if (
                conta
                and usuario_id == self.usuario_logado[0]
                and perfil_final != "admin"
            ):
                messagebox.showwarning(
                    "ViraLar",
                    "Você não pode remover seu próprio perfil de administrador."
                )
                return
            if conta and conta[3] == "admin" and conta[4] and perfil_final != "admin":
                admins_ativos = self.db.execute("""
                    SELECT COUNT(*) FROM usuarios
                    WHERE perfil = 'admin' AND ativo = 1 AND id != ?
                """, (usuario_id,)).fetchone()[0]
                if admins_ativos == 0:
                    messagebox.showwarning(
                        "ViraLar",
                        "Mantenha pelo menos um administrador ativo."
                    )
                    return

            try:
                if conta is None:
                    self.criar_usuario(
                        nome_final,
                        usuario_final,
                        senha_final,
                        perfil_final
                    )
                else:
                    self.db.execute("""
                        UPDATE usuarios SET nome = ?, usuario = ?, perfil = ?
                        WHERE id = ?
                    """, (nome_final, usuario_final, perfil_final, usuario_id))
                    if senha_final:
                        salt = secrets.token_hex(16)
                        senha_hash = self.gerar_hash_senha(senha_final, salt)
                        self.db.execute("""
                            UPDATE usuarios SET senha_hash = ?, salt = ? WHERE id = ?
                        """, (senha_hash, salt, usuario_id))
                    self.db.commit()
                    if usuario_id == self.usuario_logado[0]:
                        self.usuario_logado = (
                            usuario_id,
                            nome_final,
                            usuario_final,
                            perfil_final
                        )
            except sqlite3.IntegrityError:
                messagebox.showerror("ViraLar", "Esse nome de usuário já existe.")
                return

            janela.destroy()
            self.atualizar_tela()

        tk.Button(
            botoes,
            text="Salvar usuário",
            command=salvar_usuario,
            bg=CORES["verde"],
            fg="white",
            bd=0,
            padx=18,
            pady=9,
            cursor="hand2"
        ).pack(side="right")

    def alternar_usuario(self, tree):
        return
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showinfo("ViraLar", "Selecione um usuário primeiro.")
            return

        usuario_id = int(selecionado[0])
        conta = self.db.execute("""
            SELECT id, nome, perfil, ativo FROM usuarios WHERE id = ?
        """, (usuario_id,)).fetchone()
        if conta is None:
            messagebox.showerror("ViraLar", "Usuário não encontrado.")
            return
        if usuario_id == self.usuario_logado[0] and conta[3]:
            messagebox.showwarning("ViraLar", "Você não pode desativar sua própria conta.")
            return
        if conta[2] == "admin" and conta[3]:
            admins_ativos = self.db.execute("""
                SELECT COUNT(*) FROM usuarios
                WHERE perfil = 'admin' AND ativo = 1
            """).fetchone()[0]
            if admins_ativos <= 1:
                messagebox.showwarning(
                    "ViraLar",
                    "Mantenha pelo menos um administrador ativo."
                )
                return

        novo_status = 0 if conta[3] else 1
        acao = "desativar" if conta[3] else "ativar"
        if messagebox.askyesno(
            "Confirmar alteração",
            f"Deseja {acao} o acesso de {conta[1]}?"
        ):
            self.db.execute(
                "UPDATE usuarios SET ativo = ? WHERE id = ?",
                (novo_status, usuario_id)
            )
            self.db.commit()
            self.atualizar_tela()

    # Exibe o cabeçalho reutilizado pelas telas principais.
    def titulo(self, titulo, descricao):
        # Um método único mantém títulos e descrições visualmente consistentes.
        cabecalho = tk.Frame(
            self.conteudo,
            bg=CORES["fundo"]
        )
        cabecalho.pack(fill="x", padx=35, pady=(30, 20))

        tk.Label(
            cabecalho,
            text=titulo,
            font=("Arial", 25, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w")

        tk.Label(
            cabecalho,
            text=descricao,
            font=("Arial", 11),
            fg=CORES["cinza"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(5, 0))

    # Renderiza o painel inicial e seus indicadores.
    def mostrar_inicio(self):
        self.titulo(
            "Visão geral",
            "Acompanhe os animais e o andamento das adoções."
        )

        # Os cartões usam os mesmos dados que serão exibidos na tabela.
        dados = self.buscar_animais()

        total = len(dados)
        disponiveis = sum(a[6] == "Disponível" for a in dados)
        analise = sum(a[6] == "Em análise" for a in dados)
        adotados = sum(a[6] == "Adotado" for a in dados)

        cards = tk.Frame(
            self.conteudo,
            bg=CORES["fundo"]
        )
        cards.pack(fill="x", padx=35)

        self.card(cards, "Total de animais", total, CORES["verde"])
        self.card(cards, "Disponíveis", disponiveis, CORES["verde"])
        self.card(cards, "Em análise", analise, CORES["laranja"])
        self.card(cards, "Adotados", adotados, CORES["verde"])

        area = tk.Frame(
            self.conteudo,
            bg=CORES["painel"],
            highlightbackground=CORES["borda"],
            highlightthickness=1
        )
        area.pack(
            fill="both",
            expand=True,
            padx=35,
            pady=25
        )

        topo = tk.Frame(area, bg=CORES["painel"])
        topo.pack(fill="x", padx=20, pady=18)

        tk.Label(
            topo,
            text="Animais cadastrados",
            font=("Arial", 15, "bold"),
            fg=CORES["texto"],
            bg=CORES["painel"]
        ).pack(side="left")

        if self.tem_permissao("editar"):
            tk.Button(
                topo,
                text="+ Novo animal",
                command=self.novo_animal,
                font=("Arial", 10, "bold"),
                bg=CORES["verde"],
                fg="white",
                bd=0,
                padx=15,
                pady=8,
                cursor="hand2"
            ).pack(side="right")

        self.criar_tabela(area)

    # Renderiza um indicador numérico do painel.
    def card(self, pai, titulo, valor, cor):
        # O cartão recebe seu conteúdo por parâmetro para ser reutilizado.
        frame = tk.Frame(
            pai,
            bg=CORES["painel"],
            highlightbackground=CORES["borda"],
            highlightthickness=1
        )
        frame.pack(side="left", expand=True, fill="x", padx=(0, 12))

        tk.Label(
            frame,
            text=titulo,
            font=("Arial", 10),
            fg=CORES["cinza"],
            bg=CORES["painel"]
        ).pack(anchor="w", padx=18, pady=(16, 4))

        tk.Label(
            frame,
            text=str(valor),
            font=("Arial", 24, "bold"),
            fg=cor,
            bg=CORES["painel"]
        ).pack(anchor="w", padx=18, pady=(0, 16))

    # Monta busca, tabela e ações dos animais.
    def criar_tabela(self, pai, somente_adotados=False):
        # A mesma tabela é usada na visão geral e na tela de adoções.
        controles = tk.Frame(pai, bg=CORES["painel"])
        controles.pack(fill="x", padx=20, pady=(0, 10))

        # StringVar liga o texto digitado ao campo de busca.
        self.busca = tk.StringVar()

        entrada = tk.Entry(
            controles,
            textvariable=self.busca,
            font=("Arial", 10),
            relief="solid",
            bd=1
        )
        entrada.pack(side="left", fill="x", expand=True, ipady=7)
        entrada.insert(0, "Pesquisar por nome ou espécie")
        entrada.config(fg="#888888")

        def limpar_placeholder(event):
            # Remove o texto de exemplo quando o usuário começa a digitar.
            if entrada.get() == "Pesquisar por nome ou espécie":
                entrada.delete(0, "end")
                entrada.config(fg=CORES["texto"])

        def pesquisar(event=None):
            # Atualiza a tabela a cada tecla digitada.
            self.preencher_tabela(tree, somente_adotados)

        entrada.bind("<FocusIn>", limpar_placeholder)
        entrada.bind("<KeyRelease>", pesquisar)

        tree_frame = tk.Frame(pai, bg=CORES["painel"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        colunas = ("nome", "especie", "idade", "sexo", "porte", "status", "acoes")

        tree = ttk.Treeview(
            tree_frame,
            columns=colunas,
            show="tree headings",
            height=12
        )
        tree.heading("#0", text="Foto")
        tree.column("#0", width=66, minwidth=66, stretch=False, anchor="center")

        nomes = {
            "nome": "Nome",
            "especie": "Espécie",
            "idade": "Idade",
            "sexo": "Sexo",
            "porte": "Porte",
            "status": "Status",
            "acoes": "Ações"
        }

        larguras = {
            "nome": 140,
            "especie": 120,
            "idade": 90,
            "sexo": 90,
            "porte": 90,
            "status": 110,
            "acoes": 160
        }

        for coluna in colunas:
            tree.heading(coluna, text=nomes[coluna])
            tree.column(
                coluna,
                width=larguras[coluna],
                anchor="center"
            )

        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=tree.yview
        )
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if self.tem_permissao("editar"):
            tree.bind("<Double-1>", lambda event: self.editar_selecionado(tree))

        self.preencher_tabela(tree, somente_adotados)

        if self.tem_permissao("editar") or self.tem_permissao("status"):
            botoes = tk.Frame(pai, bg=CORES["painel"])
            botoes.pack(fill="x", padx=20, pady=(0, 20))
            if self.tem_permissao("editar"):
                tk.Button(
                    botoes,
                    text="Editar selecionado",
                    command=lambda: self.editar_selecionado(tree),
                    bg="#E8EEE9",
                    fg=CORES["texto"],
                    bd=0,
                    padx=15,
                    pady=8,
                    cursor="hand2"
                ).pack(side="left", padx=(0, 8))
                tk.Button(
                    botoes,
                    text="Excluir selecionado",
                    command=lambda: self.excluir_selecionado(tree),
                    bg=CORES["vermelho"],
                    fg="white",
                    bd=0,
                    padx=15,
                    pady=8,
                    cursor="hand2"
                ).pack(side="left", padx=8)
            if self.tem_permissao("status"):
                tk.Button(
                    botoes,
                    text="Marcar como adotado",
                    command=lambda: self.adotar_selecionado(tree),
                    bg=CORES["verde"],
                    fg="white",
                    bd=0,
                    padx=15,
                    pady=8,
                    cursor="hand2"
                ).pack(side="left", padx=8)
                tk.Button(
                    botoes,
                    text="Reabrir adoção",
                    command=lambda: self.reabrir_selecionado(tree),
                    bg=CORES["laranja"],
                    fg="white",
                    bd=0,
                    padx=15,
                    pady=8,
                    cursor="hand2"
                ).pack(side="left", padx=8)

    def preencher_tabela(self, tree, somente_adotados=False):
        # Limpa as linhas antigas antes de inserir o resultado atualizado.
        for item in tree.get_children():
            tree.delete(item)
        tree._fotos = []

        texto = self.busca.get().strip().lower()

        if texto == "pesquisar por nome ou espécie":
            texto = ""

        # A consulta é refeita para mostrar alterações recém-salvas.
        animais = self.buscar_animais()

        for animal in animais:
            animal_id, nome, especie, idade, sexo, porte, status, observacoes, caminho_imagem = animal

            # Na tela de adoções, registros com outros status são ignorados.
            if somente_adotados and status != "Adotado":
                continue

            # O filtro procura tanto no nome quanto na espécie.
            if texto and texto not in nome.lower() and texto not in especie.lower():
                continue

            foto = None
            if caminho_imagem and Path(caminho_imagem).is_file():
                try:
                    with Image.open(caminho_imagem) as imagem:
                        miniatura = ImageOps.contain(imagem.convert("RGB"), (30, 30))
                        foto = ImageTk.PhotoImage(miniatura)
                        tree._fotos.append(foto)
                except (OSError, ValueError):
                    foto = None

            tree.insert(
                "",
                "end",
                iid=str(animal_id),
                image=foto,
                values=(
                    nome,
                    especie,
                    idade,
                    sexo,
                    porte,
                    status,
                    "Duplo clique para editar" if self.tem_permissao("editar") else "Somente leitura"
                )
            )

    def mostrar_adocoes(self):
        # Reutiliza a tabela configurada para mostrar apenas adotados.
        self.titulo(
            "Adoções",
            "Consulte os animais que já encontraram uma família."
        )

        area = tk.Frame(
            self.conteudo,
            bg=CORES["painel"],
            highlightbackground=CORES["borda"],
            highlightthickness=1
        )
        area.pack(
            fill="both",
            expand=True,
            padx=35,
            pady=(0, 30)
        )

        self.criar_tabela(area, True)

    def buscar_animais(self):
        # Retorna todos os campos usados pela tabela e pelo formulário.
        return self.db.execute("""
            SELECT id, nome, especie, idade, sexo, porte, status, observacoes, imagem
            FROM animais
            ORDER BY id DESC
        """).fetchall()

    def obter_animal(self, animal_id):
        # O `?` mantém o valor separado do SQL e evita concatenar texto na consulta.
        return self.db.execute("""
            SELECT id, nome, especie, idade, sexo, porte, status, observacoes, imagem
            FROM animais
            WHERE id = ?
        """, (animal_id,)).fetchone()

    def copiar_imagem_animal(self, caminho):
        origem = Path(caminho).expanduser()
        with Image.open(origem) as imagem:
            imagem.verify()
        pasta_imagens = Path(DB).resolve().parent / "imagens_animais"
        pasta_imagens.mkdir(parents=True, exist_ok=True)
        extensao = origem.suffix.lower()
        destino = pasta_imagens / f"{uuid.uuid4().hex}{extensao}"
        shutil.copy2(origem, destino)
        return str(destino)

    def novo_animal(self):
        # Sem um ID, o formulário será tratado como novo cadastro.
        if not self.tem_permissao("editar"):
            messagebox.showerror("ViraLar", "O administrador ainda não autorizou cadastros.")
            return
        self.formulario()

    def editar_selecionado(self, tree):
        # Treeview retorna os IDs dos itens selecionados como texto.
        if not self.tem_permissao("editar"):
            messagebox.showerror("ViraLar", "O administrador ainda não autorizou edições.")
            return
        selecionado = tree.selection()

        if not selecionado:
            messagebox.showinfo(
                "ViraLar",
                "Selecione um animal para editar."
            )
            return

        self.formulario(int(selecionado[0]))

    # Abre o formulário usado tanto para cadastro quanto para edição.
    def formulario(self, animal_id=None):
        if not self.tem_permissao("editar"):
            messagebox.showerror("ViraLar", "O administrador ainda não autorizou alterações.")
            return
        # Toplevel cria uma janela independente sem perder a janela principal.
        janela = tk.Toplevel(self.root)
        janela.title("Novo animal" if animal_id is None else "Editar animal")
        janela.geometry("520x790")
        janela.resizable(False, False)
        janela.configure(bg=CORES["fundo"])
        janela.transient(self.root)
        janela.grab_set()

        # Quando há ID, os campos são preenchidos com os dados existentes.
        animal = self.obter_animal(animal_id) if animal_id else None

        tk.Label(
            janela,
            text="Novo animal" if animal_id is None else "Editar animal",
            font=("Arial", 21, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", padx=30, pady=(25, 5))

        tk.Label(
            janela,
            text="Preencha as informações do animal.",
            font=("Arial", 10),
            fg=CORES["cinza"],
            bg=CORES["fundo"]
        ).pack(anchor="w", padx=30, pady=(0, 20))

        formulario = tk.Frame(
            janela,
            bg=CORES["fundo"]
        )
        formulario.pack(fill="both", expand=True, padx=30)

        # StringVar permite que os campos sejam lidos e atualizados facilmente.
        nome = tk.StringVar(value=animal[1] if animal else "")
        especie = tk.StringVar(value=animal[2] if animal else "Cachorro")
        partes_idade = animal[3].strip().split(maxsplit=1) if animal else []
        valor_idade = partes_idade[0] if partes_idade and partes_idade[0].isdecimal() else ""
        unidade_valor = "meses" if len(partes_idade) > 1 and partes_idade[1].startswith("mes") else "anos"
        idade = tk.StringVar(value=valor_idade)
        unidade_idade = tk.StringVar(value=unidade_valor)
        sexo = tk.StringVar(value=animal[4] if animal else "Fêmea")
        porte = tk.StringVar(value=animal[5] if animal else "Médio")
        status = tk.StringVar(value=animal[6] if animal else "Disponível")

        self.campo(formulario, "Nome", nome, tipo="texto")
        self.selecao(formulario, "Espécie", especie, ["Cachorro", "Gato", "Outro"])
        self.campo(formulario, "Idade (número)", idade, tipo="numero")
        self.selecao(formulario, "Unidade da idade", unidade_idade, ["anos", "meses"])
        self.selecao(formulario, "Sexo", sexo, ["Fêmea", "Macho"])
        self.selecao(formulario, "Porte", porte, ["Pequeno", "Médio", "Grande"])
        status_campo = self.selecao(
            formulario,
            "Status",
            status,
            ["Disponível", "Em análise", "Adotado"]
        )
        if not self.tem_permissao("status"):
            status_campo.configure(state="disabled")

        imagem_path = tk.StringVar(
            value=animal[8] if animal and animal[8] else "Nenhuma imagem selecionada"
        )
        imagem_alterada = {"valor": False}
        tk.Label(
            formulario,
            text="Foto do animal",
            font=("Arial", 10, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(8, 4))
        tk.Label(
            formulario,
            textvariable=imagem_path,
            font=("Arial", 9),
            fg=CORES["cinza"],
            bg=CORES["fundo"],
            wraplength=430,
            justify="left"
        ).pack(anchor="w")
        acoes_imagem = tk.Frame(formulario, bg=CORES["fundo"])
        acoes_imagem.pack(fill="x", pady=(5, 8))

        def selecionar_imagem():
            caminho = filedialog.askopenfilename(
                parent=janela,
                title="Escolher foto do animal",
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            if caminho:
                imagem_path.set(caminho)
                imagem_alterada["valor"] = True

        def remover_imagem():
            imagem_path.set("")
            imagem_alterada["valor"] = True

        tk.Button(
            acoes_imagem,
            text="Escolher imagem",
            command=selecionar_imagem,
            bg="#E8EEE9",
            fg=CORES["texto"],
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2"
        ).pack(side="left")
        tk.Button(
            acoes_imagem,
            text="Remover imagem",
            command=remover_imagem,
            bg=CORES["painel"],
            fg=CORES["vermelho"],
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2"
        ).pack(side="left", padx=8)

        tk.Label(
            formulario,
            text="Observações",
            font=("Arial", 10, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(12, 5))

        observacoes = tk.Text(
            formulario,
            height=5,
            font=("Arial", 10),
            relief="solid",
            bd=1
        )
        observacoes.pack(fill="x")

        # Text usa índices de linha e coluna; 1.0 significa o primeiro caractere.
        if animal and animal[7]:
            observacoes.insert("1.0", animal[7])

        botoes = tk.Frame(
            janela,
            bg=CORES["fundo"]
        )
        botoes.pack(fill="x", padx=30, pady=25)

        tk.Button(
            botoes,
            text="Cancelar",
            command=janela.destroy,
            bg="#E1E6E2",
            fg=CORES["texto"],
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2"
        ).pack(side="right", padx=(8, 0))

        # Valida os campos obrigatórios e grava o cadastro no banco.
        def salvar():
            if not self.tem_permissao("editar"):
                messagebox.showerror(
                    "ViraLar",
                    "O administrador revogou sua permissão de edição."
                )
                return
            # Nome e idade são obrigatórios para evitar registros incompletos.
            if not nome.get().strip() or not idade.get().strip():
                messagebox.showwarning(
                    "ViraLar",
                    "Informe pelo menos o nome e a idade."
                )
                return

            # Remove espaços extras antes de persistir os valores.
            obs = observacoes.get("1.0", "end").strip()
            quantidade_idade = idade.get().strip()
            unidade = unidade_idade.get()
            if unidade == "anos":
                idade_formatada = f"{quantidade_idade} {'ano' if quantidade_idade == '1' else 'anos'}"
            else:
                idade_formatada = f"{quantidade_idade} {'mês' if quantidade_idade == '1' else 'meses'}"
            status_final = status.get()
            if animal_id and not self.tem_permissao("status"):
                animal_atual = self.obter_animal(animal_id)
                if animal_atual is None:
                    messagebox.showerror("ViraLar", "Esse animal não foi encontrado.")
                    return
                status_final = animal_atual[6]

            imagem_final = animal[8] if animal and animal[8] else ""
            if imagem_alterada["valor"]:
                caminho_escolhido = imagem_path.get().strip()
                try:
                    imagem_final = (
                        self.copiar_imagem_animal(caminho_escolhido)
                        if caminho_escolhido
                        else ""
                    )
                except (OSError, ValueError) as erro:
                    messagebox.showerror(
                        "ViraLar",
                        f"Não foi possível abrir essa imagem: {erro}"
                    )
                    return

            if animal_id:
                # Com ID, o botão confirma uma edição do registro existente.
                self.db.execute("""
                    UPDATE animais
                    SET nome = ?, especie = ?, idade = ?, sexo = ?,
                        porte = ?, status = ?, observacoes = ?, imagem = ?
                    WHERE id = ?
                """, (
                    nome.get().strip(),
                    especie.get(),
                    idade_formatada,
                    sexo.get(),
                    porte.get(),
                    status_final,
                    obs,
                    imagem_final,
                    animal_id
                ))
            else:
                # Sem ID, o botão confirma a criação de um novo registro.
                self.db.execute("""
                    INSERT INTO animais
                    (nome, especie, idade, sexo, porte, status, observacoes, imagem)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nome.get().strip(),
                    especie.get(),
                    idade_formatada,
                    sexo.get(),
                    porte.get(),
                    status_final,
                    obs,
                    imagem_final
                ))

            # Confirma a transação e atualiza a tela principal com os novos dados.
            self.db.commit()
            janela.destroy()
            self.atualizar_tela()

        tk.Button(
            botoes,
            text="Confirmar edição" if animal_id else "Confirmar cadastro",
            command=salvar,
            bg=CORES["verde"],
            fg="white",
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2"
        ).pack(side="right")

    def campo(self, pai, texto, variavel, tipo=None):
        # Campo de texto reutilizável para nome e idade.
        tk.Label(
            pai,
            text=texto,
            font=("Arial", 10, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(0, 5))

        entrada = tk.Entry(
            pai,
            textvariable=variavel,
            font=("Arial", 10),
            relief="solid",
            bd=1
        )

        if tipo:
            comando = pai.register(lambda valor: validar_entrada(valor, tipo))
            entrada.configure(validate="key", validatecommand=(comando, "%P"))

        entrada.pack(fill="x", ipady=7, pady=(0, 10))

    def selecao(self, pai, texto, variavel, opcoes):
        # Combobox restringe a entrada às opções válidas do cadastro.
        tk.Label(
            pai,
            text=texto,
            font=("Arial", 10, "bold"),
            fg=CORES["texto"],
            bg=CORES["fundo"]
        ).pack(anchor="w", pady=(0, 5))

        caixa = ttk.Combobox(
            pai,
            textvariable=variavel,
            values=opcoes,
            state="readonly",
            font=("Arial", 10)
        )
        caixa.pack(fill="x", ipady=5, pady=(0, 10))
        return caixa

    def id_selecionado(self, tree):
        # Centraliza a validação para as ações que dependem de uma seleção.
        selecionado = tree.selection()

        if not selecionado:
            messagebox.showinfo(
                "ViraLar",
                "Selecione um animal primeiro."
            )
            return None

        return int(selecionado[0])

    # Atualiza o status do animal após confirmação do usuário.
    def adotar_selecionado(self, tree):
        # Primeiro identifica o animal; sem seleção nenhuma alteração é feita.
        if not self.tem_permissao("status"):
            messagebox.showerror("ViraLar", "O administrador ainda não autorizou mudanças de status.")
            return
        animal_id = self.id_selecionado(tree)

        if animal_id is None:
            return

        animal = self.obter_animal(animal_id)

        if animal[6] == "Adotado":
            messagebox.showinfo(
                "ViraLar",
                "Esse animal já está marcado como adotado."
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar adoção",
            f"Marcar {animal[1]} como adotado?"
        )

        # Só altera o banco quando o usuário confirma na caixa de diálogo.
        if confirmar:
            self.db.execute(
                "UPDATE animais SET status = 'Adotado' WHERE id = ?",
                (animal_id,)
            )
            self.db.commit()
            self.atualizar_tela()

    def reabrir_selecionado(self, tree):
        # Retorna um animal adotado ao status disponível após confirmação.
        if not self.tem_permissao("status"):
            messagebox.showerror("ViraLar", "O administrador ainda não autorizou mudanças de status.")
            return
        animal_id = self.id_selecionado(tree)

        if animal_id is None:
            return

        animal = self.obter_animal(animal_id)

        confirmar = messagebox.askyesno(
            "Reabrir adoção",
            f"Reabrir o processo de {animal[1]}?"
        )

        if confirmar:
            self.db.execute(
                "UPDATE animais SET status = 'Disponível' WHERE id = ?",
                (animal_id,)
            )
            self.db.commit()
            self.atualizar_tela()

    def excluir_selecionado(self, tree):
        if not self.tem_permissao("editar"):
            messagebox.showerror("ViraLar", "O administrador ainda não autorizou exclusões.")
            return
        animal_id = self.id_selecionado(tree)

        if animal_id is None:
            return

        animal = self.obter_animal(animal_id)

        if animal is None:
            messagebox.showerror("ViraLar", "Esse animal não foi encontrado.")
            return

        confirmar = messagebox.askyesno(
            "Confirmar exclusão",
            f"Excluir o cadastro de {animal[1]}? Esta ação não pode ser desfeita."
        )

        if confirmar:
            self.db.execute("DELETE FROM animais WHERE id = ?", (animal_id,))
            self.db.commit()
            self.atualizar_tela()

    def fechar(self):
        # Fecha a conexão antes de destruir a janela para evitar recursos abertos.
        self.db.close()
        self.root.destroy()


def criar_admin_dev():
    db = sqlite3.connect(DB)
    db.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL COLLATE NOCASE UNIQUE,
            email TEXT NOT NULL DEFAULT '',
            telefone TEXT NOT NULL DEFAULT '',
            senha_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK (perfil IN ('admin', 'usuario')),
            ativo INTEGER NOT NULL DEFAULT 1,
            pode_editar INTEGER NOT NULL DEFAULT 0,
            pode_mudar_status INTEGER NOT NULL DEFAULT 0
        )
    """)
    nome = input("Nome do desenvolvedor: ").strip()
    usuario = input("Usuário administrativo: ").strip()
    senha = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirmacao = getpass.getpass("Confirme a senha: ")

    if not nome or len(usuario) < 3:
        print("Informe um nome e um usuário com pelo menos 3 caracteres.")
        db.close()
        return
    if len(senha) < 12:
        print("A senha precisa ter pelo menos 12 caracteres.")
        db.close()
        return
    if senha != confirmacao:
        print("As senhas não coincidem.")
        db.close()
        return

    salt = secrets.token_hex(16)
    senha_hash = ViraLar.gerar_hash_senha(senha, salt)
    try:
        db.execute("""
            INSERT INTO usuarios (nome, usuario, senha_hash, salt, perfil)
            VALUES (?, ?, ?, ?, 'admin')
        """, (nome, usuario, senha_hash, salt))
        db.commit()
    except sqlite3.IntegrityError:
        print("Esse usuário já existe no banco de dados.")
    else:
        print("Conta administrativa criada para uso interno.")
    finally:
        db.close()


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--criar-admin-dev":
            criar_admin_dev()
        else:
            print("Opção inválida. Use --criar-admin-dev para provisionamento interno.")
        return

    # Configura a janela e o estilo global antes de iniciar o loop do Tkinter.
    root = tk.Tk()

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure(
        "Treeview",
        background="white",
        foreground=CORES["texto"],
        rowheight=34,
        fieldbackground="white",
        font=("Arial", 10)
    )

    estilo.configure(
        "Treeview.Heading",
        background="#E8EEE9",
        foreground=CORES["texto"],
        font=("Arial", 10, "bold")
    )

    app = ViraLar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
