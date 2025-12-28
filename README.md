# Auto Kestra - Automações VIDIBR e Resultados

Repositório central para automações de extração de dados e auditoria, orquestradas pelo **Kestra** e utilizando **Playwright** para web scraping.

## 🚀 Estrutura do Projeto

O repositório está dividido em módulos independentes, cada um com sua própria lógica de workflow, páginas (POM) e scripts:

- **`flow_envio_auditoria/`**: Automação integrada com o portal VIDIBR para monitoramento de auditorias e envio de notificações detalhadas via WhatsApp.
- **`flow_envio_resultados/`**: Extração de indicadores de desempenho (Loja) e envio de resumos de metas e resultados.

## 🛠️ Stack Tecnológica

- **Orquestrador:** [Kestra](https://kestra.io/)
- **Linguagem:** Python 3.11+
- **Automação Web:** Playwright (com técnicas de Stealth para evasão)
- **Notificação:** Evolution API (WhatsApp) e Telegram (Logs de Erro)
- **Escalabilidade:** Docker / Conteinerização via Kestra

## 📂 Arquitetura (Page Object Model - POM)

Todos os projetos seguem um padrão profissional de engenharia de software para facilitar a manutenção e estabilidade:

```text
flow_X/
├── requirements.txt         # Dependências do módulo
└── workflow/
    ├── components/          # Componentes reutilizáveis (ex: Navegador)
    ├── pages/               # Page Objects (Mapeamento de elementos e ações)
    └── scripts/             # Scripts orquestradores (Lógica de negócio)
```

## ⚙️ Configuração no Kestra (KV Store)

Para o funcionamento correto dos flows, as seguintes variáveis devem estar configuradas no **KV Store** do seu Namespace no Kestra:

### Credenciais Gerais
- `GITHUB_USER`: Seu usuário do GitHub.
- `GITHUB_PASS`: Personal Access Token (PAT) para sincronização.

### Auditoria VIDIBR
- `VIDIBR_USER`: Usuário de acesso ao portal VIDIBR.
- `VIDIBR_PASS`: Senha de acesso ao portal VIDIBR.
- `ULTIMO_VIDIBR_FORM`: (Automático) Armazena o estado do último formulário processado.

### Notificações (Evolution API)
- `EVOLUTION_API_URL`: URL base da sua API Evolution.
- `EVOLUTION_API_KEY`: Chave de API da instância.
- `EVOLUTION_INSTANCE`: Nome da instância conectada.
- `WHATSAPP_GROUP_ID`: ID do grupo para auditoria.
- `WHATSAPP_GROUP_LOJA`: ID do grupo para resultados.

## 🔄 Sincronização

A sincronização entre este repositório e o Kestra é feita automaticamente através da task `SyncNamespaceFiles` presente em cada flow, garantindo que a versão em produção seja sempre a `main` deste repositório.

---
**Desenvolvido por:** [raffaelhfarias](https://github.com/raffaelhfarias)
