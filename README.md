# Bot de Monitoramento do Diário Oficial do RN

## Visão Geral

Este é um bot em Python projetado para monitorar o Diário Oficial do Estado do Rio Grande do Norte (DOERN) em busca de nomes, números de inscrição ou CPFs específicos. Ele é automatizado para rodar diariamente (ou em qualquer frequência desejada) usando GitHub Actions e envia um alerta detalhado por e-mail caso encontre alguma correspondência nova.

Este projeto nasceu da necessidade de uma ferramenta 100% confiável para acompanhar publicações de concursos públicos, superando as limitações de serviços genéricos de alerta.

## Funcionalidades Principais

- **Monitoramento Automatizado:** Executa automaticamente em horários agendados, sem necessidade de intervenção manual.
- **Busca Robusta e Híbrida:** Utiliza uma combinação de técnicas para garantir a cobertura completa:
    - **Raspagem de HTML:** Para encontrar os links das edições extras.
    - **Automação de Navegador:** Usa o Playwright para navegar em páginas complexas com JavaScript e descobrir o link direto da edição principal do dia.
    - **Extração de Texto de PDF:** Usa o `pdfplumber` para ler o conteúdo de todos os diários encontrados.
- **Lógica de Busca "Impressão Digital":** Procura por uma combinação de **Nome, Inscrição e CPF**, oferecendo alertas de alta precisão. A busca por nomes é sequencial e respeita fronteiras de palavras para minimizar drasticamente os falsos positivos.
- **Notificações por E--mail:** Envia um e-mail formatado com os detalhes de cada achado, incluindo o tipo de alerta, os dados encontrados e um link direto para o PDF.
- **Histórico Inteligente:** Mantém um registro (`historico_alertas.json`) dos PDFs que já geraram alertas para não enviar notificações repetidas sobre diários antigos, mantendo sua caixa de entrada limpa.

---

## Como Funciona: A Lógica por Trás da Magia

Entender como o bot pensa é fundamental para confiar nele.

#### O Desafio: PDFs e JavaScript

O site do Diário Oficial não oferece um link direto e previsível para a edição do dia. A edição principal é apresentada dentro de um "visualizador" carregado por JavaScript, tornando-a invisível para ferramentas simples. Este foi o nosso maior desafio de engenharia.

#### A Solução: Uma Abordagem Híbrida

- **Para as Edições Extras:** O bot primeiro varre a página principal em busca de links que terminem em `.pdf`. Estes são processados de forma rápida e direta.
- **Para a Edição do Dia:** O bot inicia um navegador "robô" (Playwright) em segundo plano. Ele acessa a página do visualizador e "espiona" as requisições de rede para capturar o link direto e secreto do arquivo PDF que é carregado, o qual está armazenado nos servidores da Amazon S3.

#### A Lógica de Busca

A busca é o coração do bot. Ela não apenas procura por palavras, mas o faz de forma inteligente:
1.  **Busca Sequencial:** Ao procurar por um nome como "Larissa Valdeci da Costa Silva", o bot verifica se "Larissa" aparece, depois se "Valdeci" aparece *depois* de "Larissa", e assim por diante.
2.  **Fronteiras de Palavra:** A busca garante que está encontrando palavras inteiras. Por exemplo, ao buscar por "Silva", ele não dará um resultado positivo para a palavra "Silvania". Isso elimina muitos falsos positivos.
3.  **Lógica OU:** O bot dispara um alerta se encontrar o `NOME` **OU** a `INSCRIÇÃO` **OU** o `CPF`, garantindo a cobertura mais ampla possível.

#### Possíveis Limitações e Desafios (Casos Extremos)

Apesar de robusto, o bot depende da qualidade do PDF. Em casos muito raros, podem ocorrer problemas:
- **PDF como Imagem:** Se uma página do Diário for salva como uma imagem em vez de texto, o conteúdo dela será invisível para o bot.
- **Texto Extremamente "Quebrado":** Em PDFs com formatação muito ruim, a ordem das palavras extraídas pode ser tão caótica que impede a busca sequencial de funcionar.
- **Nomes Muito Comuns:** Se você monitorar um nome muito comum (ex: "José da Silva") sem um número de inscrição, o alerta de "Apenas Nome" pode ser disparado com mais frequência por coincidências.

---

## Guia de Configuração Rápida (Passo a Passo)

Qualquer pessoa pode configurar este bot seguindo estes passos.

### Passo 1: Preparar o Repositório
- Crie uma conta no [GitHub](https://github.com).
- Crie um novo repositório **Público** (para ter minutos ilimitados de automação).
- Use o GitHub Codespaces (recomendado) ou clone o repositório para sua máquina para editar os arquivos.

### Passo 2: Configurar as Pessoas para Busca
- Abra o arquivo `bot.py`.
- No topo, encontre a lista `PESSOAS_PARA_BUSCAR`.
- Edite esta lista para incluir as pessoas que você deseja monitorar. Siga o formato de exemplo, preenchendo o nome completo e a inscrição. O CPF é opcional.

  ```python
  PESSOAS_PARA_BUSCAR = [
      {'nome': "Nome Completo da Pessoa 1", 'inscricao': "1234567", 'cpf': "111.222.333-44"},
      {'nome': "Nome Completo da Pessoa 2", 'inscricao': "7654321", 'cpf': ""},
  ]

### Passo 3: Gerar uma Senha de App no Google

O bot usará uma conta do Gmail para enviar os alertas. Para segurança, não usamos sua senha principal, mas uma "Senha de App".

1.  **Acesse sua Conta Google:** Vá para [myaccount.google.com](https://myaccount.google.com/).
2.  **Ative a Verificação em Duas Etapas:** Na aba "Segurança", ative a "Verificação em duas etapas". Este passo é **obrigatório** para gerar senhas de app.
3.  **Crie a Senha de App:**
    - Na mesma aba "Segurança", procure por **"Senhas de app"**.
    - Clique em "Selecionar app" e escolha **"Outro (nome personalizado)"**.
    - Dê um nome, por exemplo, `Bot Diário Oficial RN`.
    - Clique em "GERAR".
4.  **Copie a Senha:** O Google exibirá uma senha de **16 letras** em um fundo amarelo. **Copie esta senha imediatamente** e guarde-a em um local seguro. Você não a verá novamente.

### Passo 4: Configurar os Segredos (Secrets) no GitHub

Nunca coloque senhas diretamente no código. Usamos os "Secrets" do GitHub para isso.

1.  Na página do seu repositório no GitHub, vá em **`Settings`** (Configurações).
2.  No menu à esquerda, vá em **`Secrets and variables`** > **`Actions`**.
3.  Clique no botão **`New repository secret`**.
4.  Crie os 3 "secrets" abaixo, um por um:
    - **Nome do Secret:** `EMAIL_REMETENTE`
      - **Valor:** O seu e-mail do Gmail que enviará os alertas (ex: `seu.email@gmail.com`).
    - **Nome do Secret:** `EMAIL_SENHA`
      - **Valor:** A senha de 16 letras que você gerou no Passo 3.
    - **Nome do Secret:** `EMAIL_DESTINATARIO`
      - **Valor:** O e-mail que receberá as notificações (pode ser o mesmo do remetente).

### Passo 5: Personalizar o Horário (Opcional)

- Abra o arquivo `.github/workflows/monitor.yml`.
- Encontre a seção `schedule`. O `cron` define o horário de execução em UTC (3 horas à frente do horário de Brasília).
- Edite os horários conforme desejado. O exemplo abaixo roda às 6h e 18h (horário de Brasília).
  ```yaml
  schedule:
    # Roda às 9:00 UTC (6:00 BRT)
    - cron: '0 9 * * *'
    # Roda às 21:00 UTC (18:00 BRT)
    - cron: '0 21 * * *'

### Passo 6: Enviar as Alterações (Commit & Push)

- Após fazer todas as alterações, salve os arquivos.
- Vá para a aba "Source Control" no seu ambiente de edição.
- Escreva uma mensagem (ex: "Configuração inicial do bot").
- Clique em "Commit & Push" para salvar tudo no GitHub e ativar a automação.

---

## Interpretando os Alertas de E-mail

O e-mail que você receberá será formatado para te dar o máximo de informação possível:

- **Pessoa:** O nome da pessoa do seu cadastro que foi encontrada.
- **Tipo de Alerta:** A confiança do achado.
- **Itens Encontrados:** Quais dados bateram (NOME, INSCRIÇÃO, CPF).
- **Página:** O número da página no PDF.
- **Link para o Diário:** Um link clicável para abrir o PDF diretamente.

Isso permite que você avalie rapidamente a importância do alerta e verifique a fonte original com um único clique.