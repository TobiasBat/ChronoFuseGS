#include "AScreenCapturer.h"

AAScreenCapturer::AAScreenCapturer()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AAScreenCapturer::BeginPlay()
{
	Super::BeginPlay();
}

void AAScreenCapturer::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}
