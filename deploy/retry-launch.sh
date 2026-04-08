#!/bin/bash
# Auto-retry Oracle instance creation until capacity is available
# Run with: ./deploy/retry-launch.sh

COMPARTMENT_ID="ocid1.tenancy.oc1..aaaaaaaaq7gax5mvmwhbfa76qc6g57iqcvi26ah524ys46coydwppokzxgma"
IMAGE_ID="ocid1.image.oc1.eu-frankfurt-1.aaaaaaaav7j5fmkuvwreezyn7pkyyzgexm4uaobnceclctrmkj2urjvo6e5a"
SUBNET_ID="ocid1.subnet.oc1.eu-frankfurt-1.aaaaaaaaga4xvu545oqgjc7lkaiqjihfklk6euuzg5oal2dvhrp7nqf3ue2q"
SSH_KEY="$HOME/.ssh/oracle_openclaw.pub"
ADS=("UaOg:EU-FRANKFURT-1-AD-1" "UaOg:EU-FRANKFURT-1-AD-2" "UaOg:EU-FRANKFURT-1-AD-3")
RETRY_INTERVAL=120  # seconds between attempts

echo "🔄 OpenClaw Instance Launcher - Auto Retry"
echo "Versuche alle ${RETRY_INTERVAL}s bis Kapazität verfügbar..."
echo "Abbrechen mit CTRL+C"
echo ""

attempt=1
while true; do
    for AD in "${ADS[@]}"; do
        echo "[$attempt] Versuche $AD..."
        
        RESULT=$(oci compute instance launch \
          --compartment-id "$COMPARTMENT_ID" \
          --availability-domain "$AD" \
          --shape "VM.Standard.A1.Flex" \
          --shape-config '{"ocpus": 4, "memoryInGBs": 24}' \
          --image-id "$IMAGE_ID" \
          --display-name "openclaw-server" \
          --subnet-id "$SUBNET_ID" \
          --ssh-authorized-keys-file "$SSH_KEY" \
          --boot-volume-size-in-gbs 200 \
          --assign-public-ip true \
          2>&1)
        
        if echo "$RESULT" | grep -q '"lifecycle-state"'; then
            echo ""
            echo "✅ SUCCESS! Instance wird gestartet in $AD"
            
            # Get instance ID
            INSTANCE_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
            echo "Instance ID: $INSTANCE_ID"
            
            echo "⏳ Warte auf Public IP..."
            sleep 30
            
            # Get public IP
            PUBLIC_IP=$(oci compute instance list-vnics \
              --instance-id "$INSTANCE_ID" \
              --query 'data[0]."public-ip"' --raw-output 2>/dev/null)
            
            echo ""
            echo "🎉 Fertig! Verbinde dich mit:"
            echo "ssh -i ~/.ssh/oracle_openclaw ubuntu@${PUBLIC_IP}"
            echo ""
            echo "Dann installiere OpenClaw:"
            echo "scp -i ~/.ssh/oracle_openclaw -r \$(pwd) ubuntu@${PUBLIC_IP}:~/openclaw"
            exit 0
        elif echo "$RESULT" | grep -q "Out of host capacity"; then
            echo "   ❌ Keine Kapazität in $AD"
        else
            echo "   ⚠️  Unbekannter Fehler: $(echo $RESULT | head -c 100)"
        fi
    done
    
    echo ""
    echo "Alle ADs voll. Warte ${RETRY_INTERVAL}s... (Versuch $attempt)"
    echo "$(date '+%H:%M:%S') - Nächster Versuch in ${RETRY_INTERVAL}s"
    sleep $RETRY_INTERVAL
    ((attempt++))
done
