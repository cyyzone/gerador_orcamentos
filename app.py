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
    "razao_social": "NOME DA EMPRESA",
    "nome_responsavel": "NOME DO RESPONSÁVEL",
    "cnpj": "00.000.000/0001-22",
    "inscricao_municipal": "07.05.744.522-9",
    "endereco": "Endereço completo",
    "telefone": "(41) 90000-1549"
}

@app.route('/', methods=['GET', 'POST'])
def index():
    data_hoje = datetime.date.today().strftime('%d/%m/%Y')
    return render_template('index.html', empresa=DADOS_EMPRESA, data_hoje=data_hoje)

@app.route('/verificar', methods=['POST'])
def verificar_ortografia():
    spell = SpellChecker(language='pt')
    texto_servicos = request.form['servicos_inclusos']
    palavras = re.findall(r'\b\w+\b', texto_servicos.lower())
    palavras_erradas = spell.unknown(palavras)
    
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
    palavras = re.findall(r'\b\w+\b', texto_original.lower())
    palavras_erradas = spell.unknown(palavras)
    erros_com_sugestoes = {palavra: spell.correction(palavra) for palavra in palavras_erradas}
    
    texto_corrigido = texto_original
    if erros_com_sugestoes:
        for palavra_errada, sugestao in erros_com_sugestoes.items():
            if sugestao:
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
    pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(0, 10, text=DADOS_EMPRESA["razao_social"], new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 10, text=f"{DADOS_EMPRESA['nome_responsavel']} - CNPJ: {DADOS_EMPRESA['cnpj']}", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 10, text=f"Inscrição Municipal: {DADOS_EMPRESA['inscricao_municipal']}", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 10, text=DADOS_EMPRESA["endereco"], new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 10, text=DADOS_EMPRESA["telefone"], new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Título
    pdf.set_font("Helvetica", 'B', 18)
    pdf.cell(0, 10, text="ORÇAMENTO", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(5)

    # Dados do Cliente
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, text=f"Cliente: {orcamento.cliente_nome}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, text=f"Data: {orcamento.data_orcamento}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Serviços
    pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(0, 10, text="Serviços Inclusos:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    for servico in orcamento.servicos_inclusos.split('\n'):
        if servico.strip():
            pdf.cell(0, 8, text=f"- {servico}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(10)

    # Valores
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, text=f"Valor Total: R$ {orcamento.valor_total}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, text=f"Forma de Pagamento: {orcamento.forma_pagamento}", new_x="LMARGIN", new_y="NEXT")

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
