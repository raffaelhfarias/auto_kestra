import time
import re

class FormatadorWhatsapp:
    """Responsável por converter os dados brutos extraídos do IAF em uma mensagem clean para WhatsApp."""

    @staticmethod
    def _parse_percent(val_str: str) -> float:
        if not val_str or val_str == "N/D":
            return 0.0
        match = re.search(r'([\d\.,]+)%', val_str)
        if match:
            num_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(num_str)
            except ValueError:
                pass
        return 0.0

    @staticmethod
    def _parse_currency(val_str: str) -> float:
        if not val_str or val_str == "N/D":
            return 0.0
        match = re.search(r'R\$\s*([\d\.,]+)', val_str)
        if match:
            num_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(num_str)
            except ValueError:
                pass
        return 0.0

    @staticmethod
    def _get_last_line(val_str: str) -> str:
        """Pega apenas a última linha de uma string com quebras (útil pra pegar % que vem junto com pts)"""
        if not val_str:
            return "N/D"
        segs = val_str.replace('<br>', '\n').split('\n')
        for seg in reversed(segs):
            s = seg.strip()
            if s:
                return s
        return "N/D"

    @staticmethod
    def formatar(dados: dict) -> str:
        # Data e Hora de Atualização
        data_atualizacao_raw = dados.get("data_atualizacao", "N/D")
        
        # O formato bruto geralmente é "23/02/2026, às 14:42:06"
        # Queremos o formato "23/02/2026 | 14:42"
        match_dt = re.search(r'(\d{2}/\d{2}/\d{4})[^\d]*(\d{2}:\d{2})', data_atualizacao_raw)
        if match_dt:
            data_hora = f"{match_dt.group(1)} {match_dt.group(2)}"
        else:
            # Fallback
            if data_atualizacao_raw != "N/D" and data_atualizacao_raw:
                data_hora = data_atualizacao_raw
            else:
                data_hora = time.strftime("%d/%m/%Y %H:%M", time.localtime())
        
        # --- PANORAMA ---
        panorama = dados.get("panorama", {})
        pontuacao = panorama.get("pontuacao_cp", "N/D")
        atingimento = panorama.get("classificacao_pct", "N/D")
        classificacao_raw = panorama.get("classificacao", "N/D")
        
        # Emoji por classificação
        emojis_classificacao = {
            "Bronze": "🥉",
            "Prata": "🥈",
            "Ouro": "🥇",
            "Diamante": "💎",
            "Não Classificado": "⚪",
        }
        emoji_class = emojis_classificacao.get(classificacao_raw, "")
        classificacao = f"{emoji_class} {classificacao_raw} ({atingimento})".strip()
            
        rankings = panorama.get("rankings", {})
        br = rankings.get("Brasil", "N/D")
        reg = rankings.get("Regional", "N/D")
        # Pode vir como MUSK, Clube, etc
        clube = rankings.get("MUSK", rankings.get("Clube", "N/D"))

        # --- PILARES ---
        pilares_brutos = dados.get("pilares", [])
        pilares_formatados = []
        for p in pilares_brutos:
            pct_str = FormatadorWhatsapp._get_last_line(p.get("atingimento", "0%"))
            pct = FormatadorWhatsapp._parse_percent(pct_str)
            
            # Definindo cores (Farol de performance) - Verde somente para 100%
            if pct >= 100:
                icone = "🟢"
            elif pct >= 70:
                icone = "🟡"
            else:
                icone = "🔴"
                
            nome = p.get("nome", "Pilar")
            
            # Formatando a porcentagem (se for redondo tira o decimal, senão 1 casa)
            pct_formated = f"{pct:.1f}%".replace('.', ',').replace(',0%', '%')
            pilares_formatados.append({
                "pct": pct,
                "texto": f"{icone} {nome} ({pct_formated})"
            })
            
        # Ordenar os pilares do maior para o menor atingimento
        pilares_formatados.sort(key=lambda x: x["pct"], reverse=True)
        
        texto_pilares = []
        for i, p in enumerate(pilares_formatados):
            txt = p["texto"]
            # Apontar Foco Total no pior pilar se for vermelho
            if i == len(pilares_formatados) - 1 and p["pct"] < 70:
                txt += " ← Foco Total"
            texto_pilares.append(txt)

        # --- RADAR DOS INDICADORES FORA DA META ---
        indicadores = dados.get("indicadores", [])
        
        radar_linhas = []
        for ind in indicadores:
            nome = ind.get("nome", "").strip()
            habilitador = ind.get("habilitador", "").strip()
            
            # Retira indicadores vazios ou que são apenas separadores
            if not nome or nome == "N/D":
                continue
            
            # Pega valor de %
            pct_str = FormatadorWhatsapp._get_last_line(ind.get("atingimento", ""))
            pct_val = FormatadorWhatsapp._parse_percent(pct_str)
            
            is_nao_habilitado = (habilitador == "Não Habilitado")
            indicador_fora_da_meta = False
            
            # Regra específica para 2.7 (Indicador Invertido: 0 ou menor é bom)
            if "2.7 Auditoria em Lojas" in nome:
                realizado_number = FormatadorWhatsapp._parse_currency(ind.get("realizado", "0"))
                # Se for maior que 0 as auditorias, está fora da meta
                if realizado_number > 0:
                    indicador_fora_da_meta = True
                
                # Como a auditoria tem % 0.0, sobre-escrevemos o texto que irá pro output:
                pct_fmt = str(ind.get("realizado", "0").strip())
            else:
                if pct_val < 100.0:
                    indicador_fora_da_meta = True
                pct_fmt = f"{pct_val:.1f}%".replace('.', ',').replace(',0%', '%')
            
            # Adiciona ao Radar os indicadores que falharam nas regras
            if indicador_fora_da_meta or is_nao_habilitado:
                sufixo = f" (Não Habilitado)" if is_nao_habilitado else ""
                
                # Para 1.1 e 1.2, mostra o valor R$ faltante (meta - realizado)
                is_receita = ("1.1 Alcance de Meta de Receita PEF Loja" in nome or 
                              "1.2 Alcance de Meta de Receita PEF VD" in nome)
                if is_receita:
                    realizado = FormatadorWhatsapp._parse_currency(ind.get("realizado", ""))
                    meta = FormatadorWhatsapp._parse_currency(ind.get("meta", ""))
                    diff = meta - realizado
                    if diff > 0:
                        falta_valor = f"R$ {int(diff/1000)}k"
                    else:
                        falta_valor = "Batida"
                    radar_linhas.append(f"{nome}: {pct_fmt} | Falta: {falta_valor}{sufixo}")
                else:
                    radar_linhas.append(f"{nome}: {pct_fmt}{sufixo}")

        if not radar_linhas:
            radar_text = "Todos os indicadores batidos e habilitados!"
        else:
            radar_text = chr(10).join(radar_linhas)

        # Montagem do Template Final (WhatsApp usa *texto* para negrito)
        msg = f"""*Resumo IAF*
Dashboard atualizado em: {data_hora}

*STATUS ATUAL:* {pontuacao}
Atingimento: {atingimento}
Classificação: {classificacao}

*ONDE ESTAMOS:*
Brasil: {br} | Região: {reg} | Clube: {clube}

*PILARES EM DESTAQUE*
{chr(10).join(texto_pilares)}

*RADAR DE INDICADORES FORA DA META*
{radar_text}

IA Report"""
        return msg
