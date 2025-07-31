import requests
import pdfplumber
import io
import time
import json
import re
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- ESTRUTURA DE BUSCA ---
PESSOAS_PARA_BUSCAR = [
    {'nome': "Frederico Augusto Leite Lins", 'inscricao': "2021847", 'cpf': ""},
    {'nome': "Larissa Valdeci da Costa Silva", 'inscricao': "2025068", 'cpf': ""},
]

def busca_sequencial_robusta(palavras_do_nome, texto_da_pagina):
    try:
        regex_busca = r'.*?'.join(r'\b' + re.escape(p) + r'\b' for p in palavras_do_nome)
        return re.search(regex_busca, texto_da_pagina, re.IGNORECASE) is not None
    except re.error:
        return False

def processar_pdf(url_pdf, titulo_diario, session, historico):
    print(f"\n--- Processando: {titulo_diario} ---")
    print(f"URL: {url_pdf}")
    
    try:
        if url_pdf in historico:
            print("PDF já processado anteriormente. Pulando.")
            return []

        print("Baixando PDF...")
        response = session.get(url_pdf, timeout=120)
        response.raise_for_status()
        
        achados_do_pdf = []

        print("Abrindo PDF com pdfplumber...")
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            print(f"O PDF tem {len(pdf.pages)} páginas.")
            
            for i, pagina in enumerate(pdf.pages):
                print(f"Processando página {i + 1}...")
                texto_da_pagina = pagina.extract_text()
                
                if texto_da_pagina:
                    texto_da_pagina_lower = texto_da_pagina.lower().replace('\n', ' ')
                    
                    for pessoa in PESSOAS_PARA_BUSCAR:
                        nome_completo = pessoa['nome']
                        inscricao = pessoa['inscricao']
                        cpf = pessoa.get('cpf', '')

                        nome_encontrado = busca_sequencial_robusta(nome_completo.lower().split(), texto_da_pagina_lower)
                        inscricao_encontrada = inscricao and inscricao in texto_da_pagina_lower
                        cpf_encontrado = cpf and cpf in texto_da_pagina_lower

                        if nome_encontrado or inscricao_encontrada or cpf_encontrado:
                            print(f"ENCONTRADO! {nome_completo} na página {i + 1}")
                            achados_do_pdf.append({
                                'pessoa': pessoa,
                                'pagina': i + 1,
                                'url_pdf': url_pdf,
                                'titulo_diario': titulo_diario,
                                'nome_encontrado': nome_encontrado,
                                'inscricao_encontrada': inscricao_encontrada,
                                'cpf_encontrado': cpf_encontrado
                            })
                            # Para evitar múltiplos achados da mesma pessoa no mesmo PDF
                            break 
        
        print(f"Processamento concluído. Achados: {len(achados_do_pdf)}")
        return achados_do_pdf
        
    except Exception as e:
        print(f"Erro ao processar o PDF {url_pdf}: {e}")
        return []

def enviar_email_de_alerta(corpo_email):
    remetente = os.environ.get("EMAIL_REMETENTE")
    senha = os.environ.get("EMAIL_SENHA")
    destinatario = os.environ.get("EMAIL_DESTINATARIO")

    if not all([remetente, senha, destinatario]):
        print("Credenciais de e-mail não configuradas. Alerta não enviado.")
        return

    msg = MIMEText(corpo_email, 'html')
    msg['Subject'] = "Alerta de Monitoramento - Diário Oficial RN"
    msg['From'] = remetente
    msg['To'] = destinatario

    try:
        print("Conectando ao servidor de e-mail...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(remetente, senha)
            smtp_server.sendmail(remetente, destinatario, msg.as_string())
        print("E-mail de alerta enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

def buscar_edicoes_extras(session, historico):
    """Busca edições extras do diário oficial"""
    print("\n=== BUSCANDO EDIÇÕES EXTRAS ===")
    achados_extras = []
    
    try:
        print("Acessando página de edições extras...")
        response = session.get("https://www.diariooficial.rn.gov.br/dei/dorn3/", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links_encontrados = 0
        
        for link in soup.find_all('a'):
            texto_do_link = link.get_text(strip=True)
            if "Edição Extra" in texto_do_link:
                links_encontrados += 1
                url_extra = link.get('href')
                print(f"Link encontrado: {texto_do_link} -> {url_extra}")
                
                if url_extra and url_extra.endswith('.pdf'):
                    achados_extras.extend(processar_pdf(url_extra, texto_do_link, session, historico))
        
        print(f"Total de links de edições extras encontrados: {links_encontrados}")
        
    except Exception as e:
        print(f"Erro ao buscar edições extras: {e}")
    
    return achados_extras

def buscar_edicao_do_dia(session, historico):
    """Busca a edição do dia usando Playwright"""
    print("\n=== BUSCANDO EDIÇÃO DO DIA ===")
    achados_do_dia = []
    
    with sync_playwright() as p:
        try:
            print("Iniciando browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            pdf_url_interceptada = None
            
            def interceptar_requisicao(request):
                nonlocal pdf_url_interceptada
                if "cepebr-prod.s3.sa-east-1.amazonaws.com" in request.url and request.url.endswith(".pdf"):
                    pdf_url_interceptada = request.url.split('?')[0]
                    print(f"PDF interceptado: {pdf_url_interceptada}")
            
            page.on("request", interceptar_requisicao)
            
            data_hoje_obj = datetime.now()
            data_hoje_url = data_hoje_obj.strftime('%d-%m-%Y')
            titulo_diario_dia = f"Diário Oficial do Dia {data_hoje_obj.strftime('%d/%m/%Y')}"
            
            url_visualizador = f"https://deirn.sdoe.com.br/diariooficialweb/#/visualizar-jornal?dataPublicacao={data_hoje_url}&diario=MTIx&extra=false"
            print(f"Acessando: {url_visualizador}")
            
            page.goto(url_visualizador, timeout=90000)
            
            # Aguarda interceptar o PDF
            for i in range(20):
                if pdf_url_interceptada: 
                    break
                print(f"Aguardando PDF... {i+1}/20")
                time.sleep(1)
            
            browser.close()
            
            if pdf_url_interceptada:
                print(f"PDF do dia encontrado: {pdf_url_interceptada}")
                achados_do_dia.extend(processar_pdf(pdf_url_interceptada, titulo_diario_dia, session, historico))
            else:
                print("PDF do dia não foi interceptado.")
                
        except Exception as e:
            print(f"Erro com o Playwright: {e}")
    
    return achados_do_dia

def main():
    print("=== INICIANDO BOT DE MONITORAMENTO ===")
    
    # Carrega histórico
    try:
        with open("historico_alertas.json", "r") as f:
            historico = set(json.load(f))
        print(f"Histórico carregado: {len(historico)} PDFs já processados")
    except FileNotFoundError:
        historico = set()
        print("Nenhum histórico encontrado. Iniciando do zero.")

    session = requests.Session()
    todos_os_achados = []

    # 1. Busca edições extras
    todos_os_achados.extend(buscar_edicoes_extras(session, historico))

    # 2. Busca edição do dia
    todos_os_achados.extend(buscar_edicao_do_dia(session, historico))

    print(f"\n=== RESUMO FINAL ===")
    print(f"Total de achados: {len(todos_os_achados)}")

    if not todos_os_achados:
        print("Nenhum novo alerta encontrado. Encerrando.")
        return

    # Monta e envia o e-mail
    corpo_email = "<h1>🚨 Alerta de Monitoramento do Diário Oficial RN</h1>"
    corpo_email += f"<p><strong>Data/Hora:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>"
    corpo_email += f"<p>Encontramos {len(todos_os_achados)} resultado(s) novo(s):</p>"
    
    novos_pdfs_processados = set()
    
    # Agrupa os achados por pessoa para formatar o e-mail
    achados_por_pessoa = {}
    for achado in todos_os_achados:
        nome_pessoa = achado['pessoa']['nome']
        if nome_pessoa not in achados_por_pessoa:
            achados_por_pessoa[nome_pessoa] = []
        achados_por_pessoa[nome_pessoa].append(achado)

    for nome_pessoa, lista_de_achados in achados_por_pessoa.items():
        corpo_email += f"<hr><h2>📋 Resultados para: {nome_pessoa}</h2>"
        for achado in lista_de_achados:
            pagina = achado['pagina']
            url_pdf = achado['url_pdf']
            titulo_diario = achado['titulo_diario']
            
            identificadores = []
            if achado['nome_encontrado']: identificadores.append("NOME")
            if achado['inscricao_encontrada']: identificadores.append("INSCRIÇÃO")
            if achado['cpf_encontrado']: identificadores.append("CPF")
            
            corpo_email += f"""
            <div style="background: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #007cba;">
                <p><strong>📄 Fonte:</strong> {titulo_diario}</p>
                <p><strong>🔍 Itens Encontrados:</strong> {', '.join(identificadores)}</p>
                <p><strong>📖 Página:</strong> {pagina}</p>
                <p><strong>🔗 Link:</strong> <a href="{url_pdf}" target="_blank">Abrir Diário Oficial</a></p>
            </div>
            """
            novos_pdfs_processados.add(url_pdf)

    corpo_email += "<hr><p><em>Este é um alerta automático do sistema de monitoramento.</em></p>"

    print("Enviando e-mail...")
    enviar_email_de_alerta(corpo_email)

    # Atualiza e salva histórico
    historico.update(novos_pdfs_processados)
    with open("historico_alertas.json", "w") as f:
        json.dump(list(historico), f, indent=2)
    
    print(f"Histórico atualizado: {len(historico)} PDFs processados no total")
    print("=== BOT FINALIZADO ===")

if __name__ == "__main__":
    main()