# ViraLar — Controle de Adoção de Animais

![Texto alternativo](https://github.com/Davibelolima/Sistema-de-gerenciamento-para-adocao-de-animais/blob/main/docs/ViraLar_%20Conectando%20Animais%20a%20Lares-1.png?raw=true)

O ViraLar é um projeto acadêmico feito em Python para ajudar no cadastro e no acompanhamento de animais disponíveis para adoção. O sistema possui uma interface gráfica e salva as informações em um banco de dados local.

## Funcionalidades

- Cadastrar, consultar, editar e excluir animais (CRUD).
- Registrar nome, espécie, idade, sexo, porte, status, observações e foto.
- Acompanhar se o animal está disponível, com adoção em análise ou já foi adotado.
- Pesquisar animais pelo nome ou pela espécie.
- Visualizar um resumo dos animais cadastrados e seus status.
- Criar contas e acessar o sistema com login e senha.
- Controlar permissões de acesso às funções de cadastro e edição.

## Tecnologias utilizadas

- Python
- Tkinter e ttk, para a interface gráfica
- SQLite, para armazenar os dados
- Pillow, para trabalhar com as imagens

## Requisitos

- Python 3
- Tkinter
- Biblioteca Pillow

O SQLite já é disponibilizado pelo módulo `sqlite3` do Python.

## Como executar

1. Baixe ou clone o repositório.
2. Abra a pasta do projeto no terminal ou no VS Code.
3. Instale a biblioteca necessária:

   ```bash
   python -m pip install Pillow
   ```

4. Execute o arquivo principal:

   ```bash
   python viralar.py
   ```

Se o arquivo principal estiver com outro nome, use esse nome no comando.

## Como usar

1. Abra o programa e crie uma conta.
2. Entre com seu usuário e senha.
3. Consulte os animais cadastrados e use a busca para encontrar um registro.
4. Acesse a área de adoções para acompanhar o status dos animais.
5. Para cadastrar, editar ou excluir registros, a conta precisa ter as permissões necessárias. Um administrador pode gerenciar essas permissões.

## Armazenamento dos dados

As informações são guardadas em um banco de dados SQLite local. O programa também utiliza uma pasta para armazenar cópias das imagens selecionadas. Para manter os dados, faça cópias de segurança do arquivo `viralar.db` e da pasta `imagens_animais`, caso existam.

## Autores

- Davi Belo
- Marcio Marques
- Paulo Lucas

---

Projeto desenvolvido para fins acadêmicos.
