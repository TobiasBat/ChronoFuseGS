#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Disaster_Color_Gradient.generated.h"

UCLASS()
class CHRONOFUSEGS_API UDisaster_Color_Gradient : public UPrimaryDataAsset
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Colors")
	TArray<FLinearColor> ChangeGradient;
};
