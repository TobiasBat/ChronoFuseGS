// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Materials/MaterialExpression.h"
#include "MaterialExpressionComputeCov2D.generated.h"

/**
 * 
 */
UCLASS()
class DISASTER_SPLATTING_API UMaterialExpressionComputeCov2D : public UMaterialExpression
{
	GENERATED_BODY()
public:
	UMaterialExpressionComputeCov2D(const FObjectInitializer& ObjectInitializer);

	
	UPROPERTY(meta = (RequiredInput = "true", ToolTip = "Required"))
	FExpressionInput Mean;

	// UPROPERTY(EditAnywhere, Category=MaterialExpressionMyNode, meta=(OverridingInputProperty = "Mean"))
	// FVector3f DefaultMean;

	
#if WITH_EDITOR
	virtual int32 Compile(class FMaterialCompiler* Compiler, int32 OutputIndex) override;
	virtual FText GetCreationName() const override { return FText::FromString(TEXT("Compute Cov2D")); }
	virtual void GetCaption(TArray<FString>& OutCaptions) const override;
#endif
};
