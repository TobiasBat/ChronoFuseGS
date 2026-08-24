#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "DisasterSplattingModeBase.generated.h"

UCLASS()
class CHRONOFUSEGS_API ADisasterSplattingModeBase : public AGameModeBase
{
	GENERATED_BODY()

	virtual void StartPlay() override;
};
