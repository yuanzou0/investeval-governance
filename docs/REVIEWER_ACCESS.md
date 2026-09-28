# InvestEval 评审访问说明

## 提交链接

- Web 产品：<https://investeval-governance.gao44y.chatgpt.site/>
- 源代码：<https://github.com/yuanzou0/investeval-governance>

两个链接均以公开只读方式提交。评审无需登录、提供邮箱或接受邀请。公开访问不授予仓库写入、Site编辑或部署权限。

## 提交前验收

1. 使用未登录 GitHub 和 ChatGPT 的隔离浏览器会话打开两个链接。
2. 确认 GitHub 可读取 README、`src/`、`data/`、`artifacts/`、`tests/` 和 `docs/`。
3. 确认 Web 可打开五个导航，并可筛选 `ANSWER_RELEVANCE_FAILURE`、查看事实血缘和改善闭环。
4. 确认链接不依赖创建者的 cookie、登录态或本地文件。
5. 将验收日期和结果记录到提交清单。

## 失效兜底

保留一份不含 `.git`、缓存、密钥或个人信息的小于30MB提交包。包内至少包含 `README.md`、`dist/`、`src/`、`data/`、`artifacts/`、`tests/` 和 `docs/`，以及60–180秒演示视频。

## 公开安全边界

- 仓库仅含匿名合成数据，不含真实持仓、交易或KYC数据。
- 不公开API密钥、访问令牌、个人邮箱或创建者登录态。
- 静态Web中的人工复核结果仅保存于当前浏览器 `localStorage`，不会提交到服务端。
- 若未来加入真实数据或凭据，必须先分离公开演示与受限环境。
