function radarEvolutioFinal() {
  const emailDestino = "kortta.oficial@gmail.com";
  const estadosFoco = ["RO", "AC", "MT", "AM"];
  const termosAceitos = ["limpeza", "conservacao", "servicos", "administrativo", "portaria", "recepcao", "vigilancia", "zeladoria", "copeira", "jardinagem"];

  // URL Simplificada para evitar Erro 404 - Pegamos os 100 mais recentes do Brasil
  const url = "https://pncp.gov.br/api/pncp/v1/contratacoes?pagina=1&tamanhoPagina=100&ordem=dataPublicacao&asc=false";

  try {
    const resposta = UrlFetchApp.fetch(url, { "muteHttpExceptions": true });
    
    if (resposta.getResponseCode() !== 200) {
      Logger.log("Erro no PNCP: " + resposta.getResponseCode());
      return;
    }

    const corpo = JSON.parse(resposta.getContentText());
    const editais = corpo.data;
    let resultados = [];

    editais.forEach(edital => {
      const objeto = edital.objeto ? edital.objeto.toLowerCase() : "";
      const uf = edital.unidadeOrgao ? edital.unidadeOrgao.ufSigla.toUpperCase() : "";
      
      // Filtro 1: É dos nossos estados?
      const ehEstadoCerto = estadosFoco.includes(uf);
      
      // Filtro 2: Tem os nossos serviços? (Ignorando acentos para ser mais preciso)
      const temPalavra = termosAceitos.some(t => objeto.indexOf(t) !== -1);

      if (ehEstadoCerto && temPalavra) {
        resultados.push(
          "📍 ESTADO: " + uf + " | CIDADE: " + edital.unidadeOrgao.municipioNome + "\n" +
          "🏛️ ÓRGÃO: " + edital.orgaoEntidade.razaoSocial + "\n" +
          "💰 VALOR: R$ " + (edital.valorTotalEstimado || 0).toLocaleString('pt-BR') + "\n" +
          "📝 OBJETO: " + edital.objeto + "\n" +
          "🔗 LINK: " + edital.linkSistemaOrigem + "\n" +
          "------------------------------------------"
        );
      }
    });

    if (resultados.length > 0) {
      MailApp.sendEmail(
        emailDestino, 
        "🚀 RADAR EVOLUTIO: Oportunidades Encontradas!", 
        "Clayboni, detectamos " + resultados.length + " editais recentes nos estados selecionados:\n\n" + resultados.join("\n\n")
      );
      Logger.log("Sucesso! E-mail enviado com " + resultados.length + " editais.");
    } else {
      Logger.log("Varredura completa: Nenhuma licitação de serviços para RO/AC/MT/AM encontrada entre as 100 últimas postagens.");
    }

  } catch (e) {
    Logger.log("Erro técnico: " + e);
  }
}
