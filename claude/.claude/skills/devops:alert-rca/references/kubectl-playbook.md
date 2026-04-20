# kubectl RCA 플레이북 — devops:alert-rca

카테고리별 kubectl 조회 명령 목록. **조회 전용** — kubectl edit/delete 금지.

## 카테고리 A — Pod/Container

```bash
kubectl --context={ctx} -n {ns} describe pod {pod}
kubectl --context={ctx} -n {ns} logs {pod} --previous --tail=150
kubectl --context={ctx} -n {ns} get events \
  --field-selector involvedObject.name={pod} --sort-by=.lastTimestamp
```

OOMKilled 의심 시:
```bash
kubectl --context={ctx} -n {ns} top pod {pod} --containers
```

## 카테고리 B — Node/인프라

```bash
kubectl --context={ctx} describe node {node}
kubectl --context={ctx} get pods -A --field-selector spec.nodeName={node} | sort -k4 -r | head -20
kubectl --context={ctx} get events -A \
  --field-selector involvedObject.name={node} --sort-by=.lastTimestamp | tail -20
```

Karpenter 관련 시:
```bash
kubectl --context={ctx} -n infra-karpenter logs \
  -l app.kubernetes.io/name=karpenter --tail=100 --since=1h
```

참조: `claude-code/02-context/karpenter-guide.md`

## 카테고리 C — 네트워크/Istio

```bash
kubectl --context={ctx} -n {ns} logs {pod} -c istio-proxy --tail=100
kubectl --context={ctx} -n {ns} get virtualservice,destinationrule -o yaml
kubectl --context={ctx} -n istio-system get pods
kubectl --context={ctx} -n {ns} exec {pod} -c istio-proxy \
  -- pilot-agent request GET /stats \
  | grep -E "upstream_rq_5xx|upstream_cx_connect_fail|upstream_cx_overflow"
```

참조: `claude-code/02-context/istio-service-mesh.md`, `claude-code/03-guardrails/istio-troubleshooting.md`

## 카테고리 D — 스케일링

```bash
kubectl --context={ctx} -n {ns} describe hpa
kubectl --context={ctx} -n {ns} get pods | grep -E "Pending|ContainerCreating"
kubectl --context={ctx} -n {ns} describe pod {pending-pod}
kubectl --context={ctx} get nodes -o wide
```

KEDA 관련 시:
```bash
kubectl --context={ctx} -n {ns} get scaledobject -o yaml
kubectl --context={ctx} -n {ns} describe scaledobject {name}
```

참조: `claude-code/02-context/karpenter-guide.md`

## 카테고리 E — 스토리지

```bash
kubectl --context={ctx} -n {ns} describe pvc {pvc}
kubectl --context={ctx} -n {ns} get events \
  --field-selector involvedObject.kind=PersistentVolumeClaim --sort-by=.lastTimestamp
```

IDC Ceph인 경우 (`-i` 플래그 사용 — TTY 없는 환경):
```bash
kubectl --context=k8s-idc -n rook-ceph exec -i deploy/rook-ceph-tools -- ceph status
kubectl --context=k8s-idc -n rook-ceph exec -i deploy/rook-ceph-tools -- ceph df
kubectl --context=k8s-idc -n rook-ceph exec -i deploy/rook-ceph-tools -- ceph health detail
```

참조: `claude-code/03-guardrails/incident-playbooks.md`

## 카테고리 F — DB/CNPG

```bash
kubectl --context={ctx} -n {ns} get cluster -o yaml
kubectl --context={ctx} -n {ns} describe cluster {cluster-name}
kubectl --context={ctx} -n {ns} get pods -l cnpg.io/cluster={cluster-name}
kubectl --context={ctx} -n {ns} logs {primary-pod} --tail=150
```

참조: `claude-code/02-context/database-operations.md`
