# 01. Isaac Sim 설치 가이드

## 1. 시스템 요구사항

Isaac Sim은 실시간 레이트레이싱(RTX)을 사용하는 시뮬레이터라 GPU 요구사항이 까다롭습니다.

| 항목 | 최소 | 권장 |
|------|------|------|
| OS | Ubuntu 22.04 / Windows 10·11 | Ubuntu 22.04 |
| GPU | RTX 3070 (8GB) | RTX 4080/4090, RTX A5000 이상 (VRAM 16GB+) |
| CPU | Intel i7 / Ryzen 7 | i9 / Ryzen 9 이상 |
| RAM | 32GB | 64GB |
| 디스크 | SSD 50GB+ | NVMe SSD 100GB+ |
| 드라이버 | 최신 NVIDIA Production 드라이버 | 동일 |

> ❌ **지원 안 됨**: RT Core가 없는 데이터센터 GPU(A100, H100)는 렌더링 불가.
> VRAM 16GB 미만은 복잡한 씬에서 부족할 수 있음.

확인 명령 (Linux):
```bash
nvidia-smi              # GPU / 드라이버 버전 확인
ldd --version           # GLIBC 2.35 이상 필요 (pip 설치 시)
lsb_release -a          # Ubuntu 버전
```

## 2. 설치 방법 3가지

| 방법 | 추천 대상 | 특징 |
|------|-----------|------|
| **Workstation** | 입문자 (GUI로 공부) | 바이너리 다운로드 후 실행. 가장 쉬움 |
| **Pip** | Python으로 자동화/스크립트 | `pip install`로 설치. Python 3.11 + GLIBC 2.35+ |
| **Container** | 서버/클라우드/CI | Docker + NVIDIA Container Toolkit |

**공부 목적이라면 Workstation 설치를 추천합니다.**

### 2-1. Workstation 설치 (추천)

1. NVIDIA 최신 드라이버 설치 후 재부팅
   ```bash
   ubuntu-drivers devices       # 권장 드라이버 확인
   sudo ubuntu-drivers autoinstall
   sudo reboot
   ```
2. [공식 다운로드 페이지](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_workstation.html)에서
   Isaac Sim 5.1.0 바이너리(zip) 다운로드
3. 압축 해제 후 폴더에서 실행:
   ```bash
   cd ~/isaacsim
   ./isaac-sim.sh              # GUI 실행
   ```
   - 첫 실행은 셰이더 컴파일 때문에 수 분~십수 분 걸립니다 (정상).
4. 실행이 안 되면 호환성 체크:
   ```bash
   ./isaac-sim.selector.sh    # 또는 omni.isaac.sim.compatibility_checker
   ```

> 참고: 과거에는 Omniverse Launcher로 설치했지만, 최신 버전은 바이너리/​pip 중심으로 바뀌었습니다.
> 설치 화면의 정확한 절차는 버전마다 조금씩 다르니 공식 문서를 최종 기준으로 삼으세요.

### 2-2. Pip 설치 (Python 자동화용)

```bash
# Python 3.11 가상환경 권장
python3.11 -m venv ~/env_isaacsim
source ~/env_isaacsim/bin/activate
pip install --upgrade pip

# Isaac Sim 설치 (정확한 패키지명/버전은 공식 문서 확인)
pip install isaacsim[all] --extra-index-url https://pypi.nvidia.com

# 첫 실행 (EULA 동의 필요)
isaacsim
```
요구사항: Python 3.11, GLIBC 2.35+ (`ldd --version`으로 확인).

### 2-3. Container 설치 (서버/클라우드)

```bash
# NVIDIA Container Toolkit 설치 후
docker pull nvcr.io/nvidia/isaac-sim:5.1.0
docker run --name isaac-sim --entrypoint bash -it --gpus all \
  -e "ACCEPT_EULA=Y" -e "PRIVACY_CONSENT=Y" \
  nvcr.io/nvidia/isaac-sim:5.1.0
```
GUI 없이 헤드리스로 돌리고 livestream으로 화면을 받는 방식입니다. 입문 단계에서는 권장하지 않습니다.

## 3. 설치 확인

GUI가 뜨고 기본 뷰포트에 그리드가 보이면 성공입니다.
- 상단 메뉴 `Help > Welcome` 또는 `Window > Examples`에서 샘플 씬을 열어보세요.
- 로그는 `~/.nvidia-omniverse/logs/` 에 쌓입니다 (문제 발생 시 확인).

## 4. 자주 겪는 문제

| 증상 | 원인/해결 |
|------|-----------|
| 실행 직후 종료 | 드라이버 버전 불일치 → 최신 Production 드라이버 재설치 |
| 검은 화면/렌더 안 됨 | RT Core 없는 GPU이거나 VRAM 부족 |
| 첫 실행이 너무 느림 | 셰이더 캐시 생성 중. 한 번만 겪음 (정상) |
| `GLIBC` 에러 (pip) | Ubuntu 22.04 미만 → OS 업그레이드 필요 |

---
**다음 →** [02. 튜토리얼 시작하기](02-tutorials.md)

## 참고 링크
- [Isaac Sim 설치 개요](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/index.html)
- [시스템 요구사항](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)
- [Workstation 설치](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_workstation.html)
- [Pip 설치](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_python.html)
