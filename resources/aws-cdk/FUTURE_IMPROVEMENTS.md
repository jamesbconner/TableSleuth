# Future Improvements

Potential enhancements to the TableSleuth CDK infrastructure.

## Priority 1: Cost Optimization

### 1. Spot Instance Support

**Current Status:** The `ec2.Instance` L2 construct in AWS CDK does not support spot instances directly.

**Issue:** When attempting to use spot instances, the following error occurs:
```
AttributeError: module 'aws_cdk.aws_ec2' has no attribute 'SpotInstanceOptions'
```

**Root Cause:** The `ec2.Instance` construct is designed for on-demand instances only. AWS CDK does not provide a `SpotInstanceOptions` class or spot instance support for the high-level `ec2.Instance` construct.

**Current Implementation:** The CDK stack uses on-demand instances only. The `use_spot` configuration option is preserved in `cdk.json` but currently has no effect. A warning is printed if `use_spot` is set to `true`.

**Improvement:** Refactor to use Launch Templates with Auto Scaling Groups

```python
# Create launch template
launch_template = ec2.LaunchTemplate(
    self,
    "TablesleuthLaunchTemplate",
    instance_type=ec2.InstanceType(self.config.instance_type),
    machine_image=machine_image,
    security_group=self.security_group,
    role=self.instance_role,
    user_data=ec2.UserData.custom(self._get_user_data()),
    block_devices=[
        ec2.BlockDevice(
            device_name="/dev/xvda",
            volume=ec2.BlockDeviceVolume.ebs(
                volume_size=30,
                encrypted=True,
                delete_on_termination=True,
            ),
        )
    ],
)

# Create Auto Scaling Group with spot
asg = autoscaling.AutoScalingGroup(
    self,
    "TablesleuthASG",
    vpc=self.vpc,
    launch_template=launch_template,
    min_capacity=1,
    max_capacity=1,
    desired_capacity=1,
    spot_price="0.05" if self.config.use_spot else None,
)
```

**Alternative Approaches:**

**Option 1: EC2 Fleet (L1 Construct)**
```python
fleet = ec2.CfnEC2Fleet(
    self,
    "SpotFleet",
    launch_template_configs=[
        ec2.CfnEC2Fleet.FleetLaunchTemplateConfigRequestProperty(
            launch_template_specification=ec2.CfnEC2Fleet.FleetLaunchTemplateSpecificationRequestProperty(
                launch_template_id=launch_template.launch_template_id,
                version="$Latest",
            )
        )
    ],
    target_capacity_specification=ec2.CfnEC2Fleet.TargetCapacitySpecificationRequestProperty(
        total_target_capacity=1,
        default_target_capacity_type="spot",
    ),
    spot_options=ec2.CfnEC2Fleet.SpotOptionsRequestProperty(
        allocation_strategy="lowestPrice",
        instance_interruption_behavior="terminate",
    ),
)
```

**Option 2: AWS Batch**
For workloads that can tolerate interruptions:
```python
compute_env = batch.FargateComputeEnvironment(
    self,
    "SpotComputeEnv",
    vpc=self.vpc,
    spot=True,
)
```

**Cost Comparison:**

| Instance Type | On-Demand | Spot | Savings |
|---------------|-----------|------|---------|
| t3.small | ~$0.02/hour (~$15/month) | ~$0.006/hour (~$4.50/month) | 70% |
| m4.xlarge | ~$0.20/hour (~$144/month) | ~$0.06/hour (~$43/month) | 70% |

**Benefits:**
- 70% cost savings for dev/staging environments
- Configurable via `useSpot` in cdk.json
- Maintains same functionality

**Recommendation:** For the TableSleuth use case (development/testing environment), the current on-demand implementation is acceptable because:
1. **Simplicity** - The `ec2.Instance` construct is simpler and more straightforward
2. **Stability** - No risk of spot instance interruptions during analysis
3. **Cost** - Using t3.small for dev environment is already very affordable (~$15/month)
4. **Stop When Not in Use** - Users can stop the instance when not in use to save costs

If cost optimization is critical, implement Option 1 (Launch Templates with Auto Scaling Group) in a future version.

**References:**
- [AWS CDK ec2.Instance Documentation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/Instance.html)
- [AWS CDK Launch Template Documentation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/LaunchTemplate.html)
- [AWS CDK Auto Scaling Group Documentation](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_autoscaling/AutoScalingGroup.html)
- [AWS EC2 Spot Instances](https://aws.amazon.com/ec2/spot/)

## Priority 2: Security Enhancements

### 1. AWS Secrets Manager Integration

**Current:** Passwords in environment variables

**Improvement:**
```python
# Store password in Secrets Manager
password = secretsmanager.Secret(
    self,
    "GizmoSQLPassword",
    description="GizmoSQL server password",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        exclude_punctuation=True,
        password_length=32,
    ),
)

# Reference in user data
user_data.add_commands(
    f"export GIZMOSQL_PASSWORD=$(aws secretsmanager get-secret-value "
    f"--secret-id {password.secret_arn} --query SecretString --output text)"
)

# Grant read access
password.grant_read(instance.role)
```

**Benefits:**
- Automatic password generation
- Rotation support
- Audit trail via CloudTrail
- No passwords in environment variables

### 2. CloudWatch Alarms

**Add monitoring and alerting:**
```python
# CPU utilization alarm
cpu_alarm = cloudwatch.Alarm(
    self,
    "HighCPUAlarm",
    metric=instance.metric_cpu_utilization(),
    threshold=80,
    evaluation_periods=2,
    alarm_description="Alert when CPU exceeds 80%",
)

# Disk space alarm
disk_alarm = cloudwatch.Alarm(
    self,
    "LowDiskSpaceAlarm",
    metric=cloudwatch.Metric(
        namespace="CWAgent",
        metric_name="disk_used_percent",
        dimensions_map={"path": "/"},
    ),
    threshold=85,
    evaluation_periods=2,
    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
)

# Status check alarm
status_alarm = cloudwatch.Alarm(
    self,
    "StatusCheckAlarm",
    metric=instance.metric_status_check_failed(),
    threshold=1,
    evaluation_periods=2,
)
```

### 3. Systems Manager Session Manager

**Replace SSH with Session Manager:**
```python
# Add SSM permissions to role
role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name(
        "AmazonSSMManagedInstanceCore"
    )
)

# No key pair needed
# Connect via: aws ssm start-session --target <instance-id>
```

**Benefits:**
- No SSH keys to manage
- Better audit trail
- No open ports required
- Session recording

### 4. AWS Config Rules

**Add compliance monitoring:**
```python
# Ensure EBS encryption
config.ManagedRule(
    self,
    "EBSEncryptionRule",
    identifier=config.ManagedRuleIdentifiers.EC2_EBS_ENCRYPTION_BY_DEFAULT,
)

# Ensure VPC Flow Logs
config.ManagedRule(
    self,
    "VPCFlowLogsRule",
    identifier=config.ManagedRuleIdentifiers.VPC_FLOW_LOGS_ENABLED,
)
```

## Priority 2: Operational Excellence

### 5. Unit Tests

**Add infrastructure tests:**
```python
# tests/test_stack.py
from aws_cdk import assertions as assertions
import pytest

def test_vpc_created():
    app = cdk.App()
    stack = TablesleuthStack(app, "TestStack", config=test_config)
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::VPC", 1)
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": "10.10.0.0/16"
    })

def test_ebs_encryption_enabled():
    app = cdk.App()
    stack = TablesleuthStack(app, "TestStack", config=test_config)
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties("AWS::EC2::Instance", {
        "BlockDeviceMappings": [
            {
                "Ebs": {
                    "Encrypted": True
                }
            }
        ]
    })

def test_iam_least_privilege():
    app = cdk.App()
    stack = TablesleuthStack(app, "TestStack", config=test_config)
    template = assertions.Template.from_stack(stack)

    # Ensure no wildcard actions
    template.has_resource_properties("AWS::IAM::Role", {
        "Policies": assertions.Match.array_with([
            assertions.Match.object_like({
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Action": assertions.Match.not_(
                                assertions.Match.string_like_regexp(".*\\*.*")
                            )
                        })
                    ])
                }
            })
        ])
    })
```

### 6. CDK Aspects for Validation

**Automated compliance checks:**
```python
from aws_cdk import IAspect, Annotations
import jsii

@jsii.implements(IAspect)
class SecurityAspect:
    def visit(self, node):
        # Check S3 buckets have encryption
        if isinstance(node, s3.CfnBucket):
            if not node.bucket_encryption:
                Annotations.of(node).add_error(
                    "S3 buckets must have encryption enabled"
                )

        # Check EC2 instances have encrypted EBS
        if isinstance(node, ec2.CfnInstance):
            if not node.block_device_mappings:
                Annotations.of(node).add_warning(
                    "EC2 instances should have encrypted EBS volumes"
                )

        # Check security groups don't allow 0.0.0.0/0 SSH
        if isinstance(node, ec2.CfnSecurityGroup):
            for rule in node.security_group_ingress or []:
                if rule.get("FromPort") == 22 and rule.get("CidrIp") == "0.0.0.0/0":
                    Annotations.of(node).add_error(
                        "Security groups should not allow SSH from 0.0.0.0/0"
                    )

# Apply to app
Aspects.of(app).add(SecurityAspect())
```

### 7. CDK Nag

**Automated best practices validation:**
```python
from cdk_nag import AwsSolutionsChecks, NagSuppressions

# Apply AWS Solutions checks
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

# Suppress specific rules with justification
NagSuppressions.add_stack_suppressions(
    stack,
    [
        {
            "id": "AwsSolutions-IAM4",
            "reason": "Managed policies acceptable for this use case"
        }
    ]
)
```

### 8. CloudWatch Dashboard

**Add monitoring dashboard:**
```python
dashboard = cloudwatch.Dashboard(
    self,
    "TablesleuthDashboard",
    dashboard_name=f"tablesleuth-{environment}",
)

dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title="CPU Utilization",
        left=[instance.metric_cpu_utilization()],
    ),
    cloudwatch.GraphWidget(
        title="Network Traffic",
        left=[
            instance.metric_network_in(),
            instance.metric_network_out(),
        ],
    ),
    cloudwatch.SingleValueWidget(
        title="Instance Status",
        metrics=[instance.metric_status_check_failed()],
    ),
)
```

## Priority 3: Architecture Improvements

### 9. Separate Stateful Stack

**Split VPC into separate stack:**
```python
# network_stack.py
class NetworkStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "TablesleuthVPC",
            # ... configuration
        )

# compute_stack.py
class ComputeStack(Stack):
    def __init__(self, scope, construct_id, vpc, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.instance = ec2.Instance(
            self,
            "TablesleuthInstance",
            vpc=vpc,
            # ... configuration
        )

# app.py
network_stack = NetworkStack(app, "TablesleuthNetwork-dev")
compute_stack = ComputeStack(
    app,
    "TablesleuthCompute-dev",
    vpc=network_stack.vpc,
)
```

**Benefits:**
- Independent lifecycle management
- VPC can be shared across stacks
- Easier to update compute without touching network

### 10. Custom AMI with EC2 Image Builder

**Pre-bake Python and dependencies:**
```python
# Create image pipeline
image_recipe = imagebuilder.CfnImageRecipe(
    self,
    "TablesleuthRecipe",
    name="tablesleuth-recipe",
    version="1.0.0",
    parent_image="ami-xxxxx",  # Amazon Linux 2023
    components=[
        {
            "componentArn": python_component.attr_arn,
        },
        {
            "componentArn": gizmosql_component.attr_arn,
        },
    ],
)

# Use custom AMI
instance = ec2.Instance(
    self,
    "TablesleuthInstance",
    machine_image=ec2.MachineImage.generic_linux({
        "us-east-2": custom_ami_id,
    }),
)
```

**Benefits:**
- Faster instance startup (~1 minute vs ~5 minutes)
- Consistent environment
- Easier updates

### 11. Auto Scaling Group

**Support multiple instances:**
```python
asg = autoscaling.AutoScalingGroup(
    self,
    "TablesleuthASG",
    vpc=vpc,
    instance_type=instance_type,
    machine_image=machine_image,
    min_capacity=1,
    max_capacity=5,
    desired_capacity=1,
    user_data=user_data,
)

# Add scaling policies
asg.scale_on_cpu_utilization(
    "ScaleOnCPU",
    target_utilization_percent=70,
)
```

### 12. Application Load Balancer

**Add load balancer for multiple instances:**
```python
lb = elbv2.ApplicationLoadBalancer(
    self,
    "TablesleuthLB",
    vpc=vpc,
    internet_facing=True,
)

listener = lb.add_listener(
    "Listener",
    port=443,
    certificates=[certificate],
)

listener.add_targets(
    "Targets",
    port=8080,
    targets=[asg],
    health_check=elbv2.HealthCheck(
        path="/health",
        interval=cdk.Duration.seconds(30),
    ),
)
```

## Priority 4: Advanced Features

### 13. Backup and Recovery

**Automated EBS snapshots:**
```python
backup_plan = backup.BackupPlan(
    self,
    "BackupPlan",
    backup_plan_name="tablesleuth-backup",
)

backup_plan.add_rule(
    backup.BackupPlanRule(
        backup_vault=backup_vault,
        rule_name="DailyBackup",
        schedule_expression=events.Schedule.cron(
            hour="2",
            minute="0",
        ),
        delete_after=cdk.Duration.days(7),
    )
)

backup_plan.add_selection(
    "Selection",
    resources=[
        backup.BackupResource.from_ec2_instance(instance),
    ],
)
```

### 14. Cost Optimization

**Scheduled start/stop:**
```python
# Lambda function to stop instance at night
stop_function = lambda_.Function(
    self,
    "StopInstance",
    runtime=lambda_.Runtime.PYTHON_3_11,
    handler="index.handler",
    code=lambda_.Code.from_inline("""
import boto3
def handler(event, context):
    ec2 = boto3.client('ec2')
    ec2.stop_instances(InstanceIds=[event['instance_id']])
    return {'statusCode': 200}
"""),
)

# EventBridge rule to trigger at 6 PM
events.Rule(
    self,
    "StopInstanceRule",
    schedule=events.Schedule.cron(hour="18", minute="0"),
    targets=[targets.LambdaFunction(stop_function)],
)
```

### 15. Multi-Region Deployment

**Deploy to multiple regions:**
```python
# app.py
for region in ["us-east-2", "us-west-2", "eu-west-1"]:
    TablesleuthStack(
        app,
        f"TablesleuthStack-{environment}-{region}",
        config=config,
        env=cdk.Environment(
            account=os.getenv("CDK_DEFAULT_ACCOUNT"),
            region=region,
        ),
    )
```

### 16. CI/CD Pipeline

**Automated deployment:**
```python
pipeline = pipelines.CodePipeline(
    self,
    "Pipeline",
    synth=pipelines.ShellStep(
        "Synth",
        input=pipelines.CodePipelineSource.git_hub(
            "user/repo",
            "main",
        ),
        commands=[
            "npm install -g aws-cdk",
            "pip install -r requirements.txt",
            "cdk synth",
        ],
    ),
)

# Add deployment stages
pipeline.add_stage(
    TablesleuthStage(app, "Dev", config=dev_config)
)
pipeline.add_stage(
    TablesleuthStage(app, "Prod", config=prod_config),
    pre=[
        pipelines.ManualApprovalStep("PromoteToProd"),
    ],
)
```

## Implementation Priority

### Phase 1: Security (Next Sprint)
- [ ] Secrets Manager integration
- [ ] CloudWatch alarms
- [ ] Systems Manager Session Manager

### Phase 2: Testing (Following Sprint)
- [ ] Unit tests
- [ ] CDK Aspects
- [ ] CDK Nag

### Phase 3: Operations (Future)
- [ ] CloudWatch Dashboard
- [ ] Separate stateful stack
- [ ] Backup and recovery

### Phase 4: Advanced (Long-term)
- [ ] Custom AMI
- [ ] Auto Scaling
- [ ] Load Balancer
- [ ] Multi-region
- [ ] CI/CD pipeline

## Estimated Effort

| Improvement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Secrets Manager | 2 hours | High | P1 |
| CloudWatch Alarms | 1 hour | Medium | P1 |
| Session Manager | 1 hour | High | P1 |
| Unit Tests | 4 hours | High | P2 |
| CDK Aspects | 2 hours | Medium | P2 |
| CDK Nag | 1 hour | Medium | P2 |
| Dashboard | 2 hours | Low | P3 |
| Separate Stacks | 3 hours | Medium | P3 |
| Custom AMI | 8 hours | Medium | P4 |
| Auto Scaling | 4 hours | Low | P4 |
| Load Balancer | 4 hours | Low | P4 |
| CI/CD Pipeline | 8 hours | High | P4 |

## References

- [AWS CDK Patterns](https://cdkpatterns.com/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [CDK Best Practices](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html)
