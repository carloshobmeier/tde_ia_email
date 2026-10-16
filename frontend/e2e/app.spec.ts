import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function reset(page: Page, seed = true) {
  const bootstrap = await (await page.request.get('/api/bootstrap')).json();
  const headers = { 'X-Foco-Token': bootstrap.token };
  const accounts = await (await page.request.get('/api/accounts')).json();
  for (const account of accounts) await page.request.delete(`/api/accounts/${account.id}`, { headers });
  if (seed) await page.request.post('/api/demo', { headers });
  await page.goto('/');
}

test('primeiro uso e demonstração explícita', async ({ page }) => {
  await reset(page, false);
  await expect(page.getByRole('heading', { name: /Menos ruído/ })).toBeVisible();
  await page.getByRole('button', { name: 'Explorar demonstração', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Seu foco agora/ })).toBeVisible();
  await expect(page.locator('.message-row')).toHaveCount(12);
  await page.screenshot({ path: '../artifacts/dashboard.png', fullPage: true });
});

test('busca, leitura, confirmação de prazo, correção e conclusão persistem', async ({ page }) => {
  await reset(page);
  await page.getByRole('textbox', { name: 'Buscar nos seus e-mails' }).fill('matriz');
  await expect(page.locator('.message-row')).toHaveCount(1);
  await page.locator('.message-open').first().click();
  const dialog = page.getByRole('dialog', { name: 'Leitura do e-mail' });
  await expect(dialog.getByRole('heading', { name: 'Um último ajuste no projeto de IA' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Confirmar este prazo' }).click();
  await expect(dialog.getByText('Prazo confirmado por você')).toBeVisible();
  await dialog.getByRole('combobox', { name: 'Categoria', exact: true }).selectOption('trabalho');
  await expect(dialog.getByText(/Classificação corrigida por você/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Marcar como concluída' }).click();
  await expect(dialog.getByRole('button', { name: 'Reabrir ação' })).toBeVisible();
  await page.screenshot({ path: '../artifacts/message.png' });
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Concluídos', exact: true }).click();
  await expect(page.locator('.message-row')).toHaveCount(1);
  await page.locator('.message-open').click();
  await expect(dialog.getByRole('combobox', { name: 'Categoria', exact: true })).toHaveValue('trabalho');
});

test('favoritos, temas e atalho de busca', async ({ page }) => {
  await reset(page);
  await page.locator('.row-star').first().click();
  await page.getByRole('button', { name: 'Favoritos', exact: true }).click();
  await expect(page.locator('.message-row')).toHaveCount(1);
  await page.getByRole('button', { name: 'Usar tema escuro' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('textbox', { name: 'Buscar nos seus e-mails' })).toBeFocused();
  await page.screenshot({ path: '../artifacts/dark.png' });
});

test('importação de eml, reimportação e conteúdo seguro', async ({ page }) => {
  await reset(page, false);
  const mail = 'From: Teste <test@example.com>\r\nSubject: Importacao segura\r\nDate: Fri, 25 Sep 2026 10:00:00 -0300\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Confira o relatorio.</p><script>alert(1)</script><img src="https://tracker.example/x" />';
  const requests: string[] = [];
  page.on('request', request => requests.push(request.url()));
  await page.getByLabel('Importar arquivos de e-mail').setInputFiles({ name: 'teste.eml', mimeType: 'message/rfc822', buffer: Buffer.from(mail) });
  await expect(page.locator('.message-row')).toHaveCount(1);
  await page.locator('.message-open').click();
  await page.getByRole('button', { name: 'Mensagem original' }).click();
  await expect(page.locator('.original-body')).toHaveText('Confira o relatorio.');
  expect(requests.some(url => url.includes('tracker.example'))).toBe(false);
  await page.keyboard.press('Escape');
  await page.getByLabel('Importar arquivos de e-mail').setInputFiles({ name: 'teste.eml', mimeType: 'message/rfc822', buffer: Buffer.from(mail) });
  await expect(page.getByRole('status')).toContainText('já estavam aqui');
  await expect(page.locator('.message-row')).toHaveCount(1);
});

test('navegação móvel sem transbordamento', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await reset(page);
  await expect(page.getByRole('heading', { name: /Seu foco agora/ })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.getByRole('button', { name: 'Abrir navegação' }).click();
  await page.getByRole('button', { name: 'Configurações', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Um espaço seu/ })).toBeVisible();
  await page.screenshot({ path: '../artifacts/mobile.png', fullPage: true });
});

test('avaliação explicita dados sintéticos e exporta resultados reais do treino', async ({ page }) => {
  await reset(page);
  await page.getByRole('button', { name: 'Inteligência & dados', exact: true }).click();
  await expect(page.getByText('Avaliação inicial com dados sintéticos')).toBeVisible();
  await expect(page.locator('.confusion-matrix tbody tr')).toHaveCount(5);
  await page.getByRole('button', { name: 'Prioridades', exact: true }).click();
  await expect(page.locator('.confusion-matrix tbody tr')).toHaveCount(3);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar avaliação' }).click();
  expect((await download).suggestedFilename()).toBe('foco-avaliacao.json');
  await page.screenshot({ path: '../artifacts/evaluation.png', fullPage: true });
});

test('interface funciona com tráfego externo bloqueado', async ({ page }) => {
  // Bloqueia inclusive scripts injetados pelo software de segurança da máquina de teste.
  await page.route('**/*', route => route.request().url().startsWith('http://127.0.0.1:8770') ? route.continue() : route.abort());
  await reset(page);
  await expect(page.getByRole('heading', { name: /Seu foco agora/ })).toBeVisible();
  await page.locator('.message-open').first().click();
  await expect(page.locator('.summary-text')).toBeVisible();
  await page.getByRole('button', { name: 'Mensagem original' }).click();
  await expect(page.locator('.original-body')).toContainText('matriz de confusão');
});

test('acessibilidade da visão principal em temas claro e escuro', async ({ browser }) => {
  const context = await browser.newContext({ bypassCSP: true });
  const page = await context.newPage();
  await reset(page);
  await expect(page.getByRole('heading', { name: /Seu foco agora/ })).toBeVisible();
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: 'Usar tema escuro' }).click();
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), theme).toEqual([]);
  }
  await context.close();
});
