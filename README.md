# Personal Finance MCP

개인 자산 정보(마이데이터)를 LLM 모델과 연동하여 세밀한 자산 관리 피드백을 제공하는 프로젝트입니다.<br/>
[MCP(Model Context Protocol)](https://modelcontextprotocol.io)를 활용하여 LLM 모델은 개인의 자산 정보를 이해하고 사용자 요구사항에 맞춰 최적의 분석 결과를 제공할 수 있도록 합니다.

지금은 다음 기능에 대한 [도구(Tool)](https://modelcontextprotocol.io/docs/learn/server-concepts#tools)를 LLM 모델에게 제공합니다.
* get_enabled_bank_accounts: 사용자가 활성화한 계좌 정보를 LLM 모델에 전달합니다.
* get_bank_transactions: 계좌에 대한 입금, 출금 거래기록을 LLM 모델에 전달합니다.
* get_enabled_card_accounts: 사용자가 활성화한 카드 정보를 LLM 모델에 제공합니다.
* get_card_transactions: 신용/체크 카드에 대한 이용 기록을 LLM 모델에 제공합니다.

<table>
    <tr>
        <th width="50%">Dashboard</th>
        <th width="50%">on Claude Desktop (Claude Sonnet)</th>
    </tr>
    <tr>
        <td><img src=".github/dashboard.png"  align="center" /></td>
        <td rowspan="3"><img src=".github/claude_desktop.png" align="center" /></td>
    </tr>
    <tr>
         <th>on Antigravity (Gemini 3.0 Flash)</th>
    </tr>
    <tr>
        <td><img src=".github/antigravity.png" align="center" /></td>
    </tr>
</table>

## 1. Motivation 🎯

## 2. MCP Architecture 🏗️

## 3. Getting Started 🚀
**Requirements**
* Python 3.14+
* [Codef API](https://codef.io/) Client ID, Client Secret and Public Key 

**Installation**
```bash
# Clone the repository
$ git clone https://github.com/gunyu1019/personal_finance_mcp.git
$ cd personal_finance_mcp

# Create a virtual environment
$ python -m venv venv
$ source venv/bin/activate

# Install dependencies
$ pip install -r requirements.txt

# Setup the configuration file
$ cp .env.example .env
```


**Configuration File**
```dotenv
# .env

# 서버 설정
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# 애플리케이션 대시보드에 로그인하기 위한 비밀번호입니다.
ROOT_PASSWORD=changeme

# 데이터베이스 연결 URL
DATABASE_URL=sqlite+aiosqlite:///./mydata.db

# CODEF API 연동 정보
CODEF_MODE=demo  # sandbox, demo or live
CODEF_CLIENT_ID=your_codef_client_id
CODEF_CLIENT_SECRET=your_codef_client_secret
CODEF_PUBLIC_KEY=your_codef_public_key

# 보안 설정 관련 상수 키입니다.
# 그대로 냅두시면 됩니다.
ADMIN_COOKIE_NAME=admin_session
TOKEN_EXPIRE_HOURS=12
JWT_ALGORITHM=HS256
JWT_SUBJECT=admin
SSE_RETRY_TIMEOUT=15000

# 민감 정보를 보호가 위한 AES-256 대칭키 암호화 키입니다.
# 서버 첫 실행 시 로그에 출력되는 Fernet 키 문자열을 그대로 넣으세요.
ENCRYPTION_SECRET_KEY=
```

**Run**
```bash
$ python -m uvicorn app.main:app --reload 
```

## 4. Use Cases 💡

## 5. Project Structure 📁

## 6. Disclaimer ⚠️
* **비전문적 조언:** <br/>
  본 프로젝트와 연동된 LLM이 제공하는 자산 분석, 가계부 작성, 재무 관련 답변은 **__참고용__**일 뿐이며, 전문적인 재무 상담이나 투자 권유를 대체할 수 없습니다.


* **AI 환각(Hallucination) 주의:** <br/>
  생성형 AI의 특성상 부정확하거나 지어낸 정보를 제공할 수 있습니다. 
  실제 금전적인 의사결정이나 중요한 거래 전에는 반드시 실제 금융사의 공식 데이터를 직접 교차 검증하시기 바랍니다.


* **면책 조항:** <br/>
  본 프로젝트를 사용하면서 발생하는 데이터 유출(환경 변수 유출, 사용자 기기 보안 취약점 등) 및 LLM의 답변으로 인한 직/간접적 손실에 대한 모든 책임은 사용자 본인에게 있으며, 프로젝트 개발자 및 기여자는 어떠한 법적 책임도 지지 않습니다. 
  또한 소프트웨어를 사용하여 데이터를 수집하는 과정에서 **특정 금융사 또는 API 제공자의 이용약관(스크래핑 금지 조항, 과도한 트래픽 유발 등)을 위반하여 발생하는 계정 잠금, 서비스 이용 정지, 법적 분쟁** 등에 대해 프로젝트 개발자는 일절 책임을 지지 않습니다.

## 7. License 📄
This project is licensed under the [BSD 3-Clause License](LICENSE) - see the LICENSE file for details.