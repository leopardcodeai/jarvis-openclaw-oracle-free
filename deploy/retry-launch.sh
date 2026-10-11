#!/bin/bash
# Auto-retry Oracle instance creation until capacity is available
# Tries: 2 OCPUs / 12 GB first, falls back to 1 OCPU / 6 GB
# Run with: ./deploy/retry-launch.sh

COMPARTMENT_ID="ocid1.tenancy.oc1..aaaaaaaaq7gax5mvmwhbfa76qc6g57iqcvi26ah524ys46coydwppokzxgma"
IMAGE_ID="ocid1.image.oc1.eu-frankfurt-1.aaaaaaaav7j5fmkuvwreezyn7pkyyzgexm4uaobnceclctrmkj2urjvo6e5a"
SUBNET_ID="ocid1.subnet.oc1.eu-frankfurt-1.aaaaaaaaga4xvu545oqgjc7lkaiqjihfklk6euuzg5oal2dvhrp7nqf3ue2q"
SSH_KEY="$HOME/.ssh/oracle_openclaw.pub"
ADS=("UaOg:EU-FRANKFURT-1-AD-1" "UaOg:EU-FRANKFURT-1-AD-2" "UaOg:EU-FRANKFURT-1-AD-3")
RETRY_INTERVAL=120  # seconds between attempts

# Shape configs to try in order
SHAPES=(
    '{"ocpus": 2, "memoryInGBs": 12}'
    '{"ocpus": 1, "memoryInGBs": 6}'
)
SHAPE_LABELS=(
    "2 OCPUs / 12 GB RAM"
    "1 OCPU  / 6 GB RAM"
)

echo "🔄 Jarvis Instance Launcher - Auto Retry"
echo "Reihenfolge: 2 OCPUs/12GB → 1 OCPU/6GB"
echo "Versuche alle ${RETRY_INTERVAL}s bis Kapazität verfügbar..."
echo "Abbrechen mit CTRL+C"
echo ""

_try_launch() {
    local AD="$1"
    local SHAPE_CONFIG="$2"
    local LABEL="$3"

    RESULT=$(oci compute instance launch \
      --compartment-id "$COMPARTMENT_ID" \
      --availability-domain "$AD" \
      --shape "VM.Standard.A1.Flex" \
      --shape-config "$SHAPE_CONFIG" \
      --image-id "$IMAGE_ID" \
      --display-name "jarvis-server" \
      --subnet-id "$SUBNET_ID" \
      --ssh-authorized-keys-file "$SSH_KEY" \
      --boot-volume-size-in-gbs 200 \
      --assign-public-ip true \
      2>&1)

    if echo "$RESULT" | grep -q '"lifecycle-state"'; then
        echo ""
        echo "✅ SUCCESS! Instance ($LABEL) startet in $AD"

        INSTANCE_ID=$(echo "$RESULT" | /opt/homebrew/bin/python3.12 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null || echo "$RESULT" | grep '"id"' | head -1 | sed 's/.*"id": "\(.*\)".*/\1/')
        echo "Instance ID: $INSTANCE_ID"

        echo "⏳ Warte auf Public IP..."
        sleep 30

        PUBLIC_IP=$(oci compute instance list-vnics \
          --instance-id "$INSTANCE_ID" \
          --query 'data[0]."public-ip"' --raw-output 2>/dev/null)

        echo ""
        echo "🎉 Fertig! ($LABEL)"
        echo "ssh -i ~/.ssh/oracle_openclaw ubuntu@${PUBLIC_IP}"
        echo ""
        echo "Deploy:"
        echo "scp -i ~/.ssh/oracle_openclaw -r \$(pwd) ubuntu@${PUBLIC_IP}:~/openclaw"
        return 0
    elif echo "$RESULT" | grep -q "Out of host capacity"; then
        return 1  # no capacity
    else
        echo "   ⚠️  Fehler: $(echo "$RESULT" | head -c 120)"
        return 2  # other error
    fi
}

attempt=1
while true; do
    found=false

    for i in "${!SHAPES[@]}"; do
        SHAPE_CONFIG="${SHAPES[$i]}"
        LABEL="${SHAPE_LABELS[$i]}"

        for AD in "${ADS[@]}"; do
            echo "[$attempt] ${LABEL} → $AD"

            _try_launch "$AD" "$SHAPE_CONFIG" "$LABEL"
            STATUS=$?

            if [ $STATUS -eq 0 ]; then
                found=true
                break 2
            elif [ $STATUS -eq 1 ]; then
                echo "   ❌ Keine Kapazität"
            fi
        done

        echo "   → ${LABEL}: alle ADs voll, versuche kleinere Größe..."
    done

    echo ""
    echo "Alle Größen & ADs voll. Warte ${RETRY_INTERVAL}s... (Versuch $attempt)"
    echo "$(date '+%H:%M:%S') - Nächster Versuch in ${RETRY_INTERVAL}s"
    sleep $RETRY_INTERVAL
    ((attempt++))
done
