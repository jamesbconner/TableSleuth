# EC2 Key Pair Management in CDK

## The Challenge

AWS CDK (via CloudFormation) can create EC2 key pairs, but it doesn't provide direct access to the private key material. This is a security feature - CloudFormation stores the private key in AWS Systems Manager Parameter Store instead of exposing it in stack outputs.

## How It Works

When CDK creates a key pair:
1. CloudFormation generates the key pair
2. Private key is stored in AWS Systems Manager Parameter Store
3. Key pair name is available in stack outputs
4. Private key must be retrieved manually from Parameter Store

This approach provides better security than storing keys locally.

## Solutions

### Option 1: Retrieve from Parameter Store (Recommended)

After deploying the stack, retrieve the private key:

```bash
# Get key pair ID from CloudFormation
KEY_PAIR_ID=$(aws cloudformation describe-stacks \
  --stack-name TablesleuthStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KeyPairId`].OutputValue' \
  --output text)

# Retrieve private key
aws ssm get-parameter \
  --name /ec2/keypair/$KEY_PAIR_ID \
  --with-decryption \
  --query Parameter.Value \
  --output text > tablesleuth-ssh-key.pem

chmod 600 tablesleuth-ssh-key.pem
```

### Option 2: Use Existing Key Pair

If you already have a key pair, modify the stack to use it:

```python
# In tablesleuth_stack.py, replace _create_key_pair() with:
def _create_key_pair(self) -> ec2.IKeyPair:
    """Use existing key pair."""
    return ec2.KeyPair.from_key_pair_name(
        self,
        "ExistingKeyPair",
        "your-existing-key-name"
    )
```

### Option 3: Use AWS Console

1. Go to EC2 → Key Pairs in AWS Console
2. Find `tablesleuth-ssh-key`
3. Click "Actions" → "Retrieve key pair"
4. Copy the private key and save to file

### Option 4: Custom Resource (Advanced)

Create a CDK custom resource that:
1. Creates the key pair via boto3
2. Saves private key to Secrets Manager
3. Returns the secret ARN

This requires additional Lambda function code.

## Security Benefits

The CDK approach provides better security than direct key pair creation:
- Private keys stored in AWS Parameter Store
- Encrypted at rest
- Access controlled via IAM
- Audit trail via CloudTrail
- No local files to manage
- Centralized secrets management

## Future Improvements

Potential enhancements to the CDK stack:

1. **Add custom resource** to automatically retrieve and output the private key
2. **Store in Secrets Manager** instead of Parameter Store for better secret management
3. **Add rotation** for key pairs (though EC2 key pairs don't support rotation)
4. **Document in outputs** with clear instructions on retrieval

## Related AWS Documentation

- [EC2 Key Pairs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
- [CloudFormation Key Pair Resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-keypair.html)
- [Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
