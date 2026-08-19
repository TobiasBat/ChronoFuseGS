// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "DisasterSplattingModeBase.generated.h"

/**
 * 
 */
UCLASS()
class DISASTER_SPLATTING_API ADisasterSplattingModeBase : public AGameModeBase
{
	GENERATED_BODY()


	virtual void StartPlay() override;
};
