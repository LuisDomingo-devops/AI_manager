import re
import sys

def process(filepath, is_mail=False):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if not is_mail:
        content = re.sub(r'^(import os)$', r'import os\nfrom app.utils.logger import app_logger', content, flags=re.MULTILINE)
        content = re.sub(r'except Exception:\n(\s+)pass', r'except Exception as e:\n\1app_logger.warning(f"Error silencioso capturado: {e}")', content)
        content = re.sub(r'except Exception:\s+pass', r'except Exception as e: app_logger.warning(f"Error silencioso capturado: {e}")', content)
    else:
        content = re.sub(r'except Exception:\n(\s+)pass', r'except Exception as e:\n\1tool_logger.warning(f"Error en mail_tools: {e}")', content)
        content = re.sub(r'except BaseException:\n(\s+)pass', r'except BaseException as e:\n\1tool_logger.warning(f"BaseException en mail_tools: {e}")', content)
        content = re.sub(r'except Exception:\s+pass', r'except Exception as e: tool_logger.warning(f"Error en mail_tools: {e}")', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

process('app/domain/services/bank_service.py', is_mail=False)
process('app/tools/server/mail_tools.py', is_mail=True)
