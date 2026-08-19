// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Disaster_Color_Gradient.generated.h"

/**
 * 
 */
UCLASS()
class DISASTER_SPLATTING_API UDisaster_Color_Gradient : public UPrimaryDataAsset
{
	GENERATED_BODY()
public:
	// This is the variable your Actor will look for
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Colors")
	TArray<FLinearColor> ChangeGradient;
};
