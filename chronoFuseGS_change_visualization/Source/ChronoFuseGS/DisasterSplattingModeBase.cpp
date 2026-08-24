#include "DisasterSplattingModeBase.h"

void ADisasterSplattingModeBase::StartPlay()
{
	Super::StartPlay();
	check(GEngine != nullptr);
	GEngine->AddOnScreenDebugMessage(-1, 2.0f, FColor::White, "Disaster Splatting has started");
}
