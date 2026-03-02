from flask import Flask, render_template, request, url_for, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from fpdf import FPDF
from spellchecker import SpellChecker
import os
import datetime
import re
import io

app = Flask(__name__)
app.secret_key = 'agora-vai-funcionar-com-certeza-2025'

# Configuração da Base de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orcamentos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo da Tabela
class Orcamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(100), nullable=False)
    data_orcamento = db.Column(db.String(20), nullable=False)
    servicos_inclusos = db.Column(db.Text, nullable=False)
    valor_total = db.Column(db.String(50), nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=False)

# Cria a base de dados automaticamente
with app.app_context():
    db.create_all()

DADOS_EMPRESA = {
    "razao_social": "VCS REFORMAS EM GERAL",
    "nome_responsavel": "VALTEMIRO CAETANO DE SOUZA",
    "cnpj": "23.947.352/0001-54",
    "inscricao_municipal": "07.06.736.521-8",
    "endereco": "Rua Tenente José Carlos Lopes de Souza, 42 A - Borda do Campo - SJP",
    "telefone": "(41) 3282-9499 / (41) 98522-1549"
}

@app.route('/', methods=['GET', 'POST'])
def index():
    data_hoje = datetime.date.today().strftime('%d/%m/%Y')
    return render_template('index.html', empresa=DADOS_EMPRESA, data_hoje=data_hoje)

@app.route('/verificar', methods=['POST'])
def verificar_ortografia():
    spell = SpellChecker(language='pt')
    
    # Carrega o dicionário logo na primeira verificação
    try:
        spell.word_frequency.load_text_file('./dicionario_construcao.txt')
    except Exception as e:
        print(f"Erro ao carregar dicionário: {e}")
        
    texto_servicos = request.form['servicos_inclusos']
    
    # Extrai as palavras preservando as letras maiúsculas e minúsculas originais
    palavras_originais = re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', texto_servicos)
    
    # Seleciona apenas as palavras que não começam com letra maiúscula
    palavras_para_verificar = [p.lower() for p in palavras_originais if not p[0].isupper()]
    
    palavras_erradas = spell.unknown(palavras_para_verificar)
    
    dados_completos = {key: value for key, value in request.form.items()}

    if palavras_erradas:
        erros_com_sugestoes = {palavra: spell.correction(palavra) for palavra in palavras_erradas}
        session['dados_formulario'] = dados_completos
        session['erros_ortografia'] = erros_com_sugestoes
        return redirect(url_for('pagina_correcao'))
    else:
        return gerar_orcamento(dados_completos)

@app.route('/corrigir')
def pagina_correcao():
    dados = session.get('dados_formulario', {})
    erros = session.get('erros_ortografia', {})
    return render_template('corrigir.html', erros=erros, dados=dados)

@app.route('/preview', methods=['POST'])
def preview_correcao():
    dados_formulario = {key: value for key, value in request.form.items()}
    texto_original = dados_formulario.get('servicos_inclusos', '')
    
    spell = SpellChecker(language='pt')
    try:
        spell.word_frequency.load_text_file('./dicionario_construcao.txt')
    except Exception as e:
        print(f"Erro ao carregar dicionário em /preview: {e}")
        
    palavras_originais = re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', texto_original)
    palavras_para_verificar = [p.lower() for p in palavras_originais if not p[0].isupper()]
    
    palavras_erradas = spell.unknown(palavras_para_verificar)
    erros_com_sugestoes = {palavra: spell.correction(palavra) for palavra in palavras_erradas}
    
    texto_corrigido = texto_original
    if erros_com_sugestoes:
        for palavra_errada, sugestao in erros_com_sugestoes.items():
            if sugestao:
                # Garante que a substituição ignora maiúsculas e minúsculas
                texto_corrigido = re.sub(r'\b' + re.escape(palavra_errada) + r'\b', sugestao, texto_corrigido, flags=re.IGNORECASE)
    
    dados_formulario['servicos_inclusos'] = texto_corrigido
    return render_template('corrigir.html', erros=erros_com_sugestoes, dados=dados_formulario)

@app.route('/gerar', methods=['POST'])
def gerar_rota():
    dados_formulario = {key: value for key, value in request.form.items()}
    return gerar_orcamento(dados_formulario)

def gerar_orcamento(dados):
    # Formata os serviços para guardar na base de dados
    servicos_lista = [s.strip().capitalize() for s in dados["servicos_inclusos"].splitlines() if s.strip()]
    servicos_texto = "\n".join(servicos_lista)
    
    novo_orcamento = Orcamento(
        cliente_nome=dados['cliente_nome'],
        data_orcamento=dados['data_orcamento'],
        servicos_inclusos=servicos_texto,
        valor_total=dados['valor_total'],
        forma_pagamento=dados['forma_pagamento']
    )
    
    db.session.add(novo_orcamento)
    db.session.commit()
    
    return redirect(url_for('historico'))

@app.route('/historico')
def historico():
    orcamentos = Orcamento.query.order_by(Orcamento.id.desc()).all()
    return render_template('historico.html', orcamentos=orcamentos)

@app.route('/baixar_pdf/<int:id>')
def baixar_pdf(id):
    orcamento = Orcamento.query.get_or_404(id)

    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho da Empresa
    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(0, 8, text="VCS REFORMAS EM GERAL", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, text="VALTEMIRO CAETANO DE SOUZA", new_x="LMARGIN", new_y="NEXT")
    
    # CNPJ (rótulo em negrito, número normal)
    pdf.set_font("Helvetica", 'B', 11)
    largura_cnpj = pdf.get_string_width("CNPJ: ") + 1
    pdf.cell(largura_cnpj, 8, text="CNPJ: ")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 8, text="23.947.352/0001-54", new_x="LMARGIN", new_y="NEXT")
    
    # Inscrição Municipal (rótulo em negrito, número normal)
    pdf.set_font("Helvetica", 'B', 11)
    largura_im = pdf.get_string_width("Inscrição Municipal: ") + 1
    pdf.cell(largura_im, 8, text="Inscrição Municipal: ")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 8, text="07.06.736.521-8", new_x="LMARGIN", new_y="NEXT")
    
    # Endereço e telefone (texto normal)
    pdf.cell(0, 8, text="Rua Tenente José Carlos Lopes de Souza, 42 A - Borda do Campo - SJP", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, text="(41) 3282-9499 / (41) 98522-1549", new_x="LMARGIN", new_y="NEXT")
    
    # Linha tracejada
    pdf.ln(4)
    pdf.cell(0, 6, text="--------------------------------------------------", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Título (Centralizado e maior)
    pdf.set_font("Helvetica", 'B', 18)
    pdf.cell(0, 10, text="Orçamento", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Dados do Cliente
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 8, text=f"Cliente: {orcamento.cliente_nome}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, text=f"Data: {orcamento.data_orcamento}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Serviços (Cor Azul e Negrito)
    pdf.set_font("Helvetica", 'B', 12)
    # Define a cor do texto para azul
    pdf.set_text_color(68, 114, 196) 
    pdf.cell(0, 8, text="Serviços Inclusos:", new_x="LMARGIN", new_y="NEXT")
    
    # Volta a cor para preto e o texto para normal
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", '', 11)
    
    # Lista de Serviços com marcadores de traço
    for servico in orcamento.servicos_inclusos.split('\n'):
        if servico.strip():
            pdf.cell(0, 7, text=f"- {servico.strip()}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(8)

    # Valores
    pdf.set_font("Helvetica", 'B', 11)
    largura_valor = pdf.get_string_width("Valor Total: ") + 1
    pdf.cell(largura_valor, 8, text="Valor Total: ")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 8, text=f"R$ {orcamento.valor_total}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", 'B', 11)
    largura_pagamento = pdf.get_string_width("Forma de Pagamento: ") + 1
    pdf.cell(largura_pagamento, 8, text="Forma de Pagamento: ")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 8, text=f"{orcamento.forma_pagamento}", new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()
    nome_seguro = re.sub(r'[^a-zA-Z0-9_.-]', '_', orcamento.cliente_nome).lower()

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"orcamento_{nome_seguro}.pdf"
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')